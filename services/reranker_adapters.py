"""Reranker model registry and per-model adapters for the remote service.

The service deliberately does not treat every reranker as the same
SentenceTransformer CrossEncoder. Stable CrossEncoder models use the generic
adapter; Qwen/Jina are isolated behind model-specific adapters and validation so
an experimental failure cannot poison the whole service.
"""
from __future__ import annotations

import logging
import math
import os
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Iterable

MMINILM_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
BGE_MODEL = "BAAI/bge-reranker-v2-m3"
QWEN3_MODEL = "Qwen/Qwen3-Reranker-0.6B"
JINA_MODEL = "jinaai/jina-reranker-v2-base-multilingual"

SUPPORTED_MODELS = (MMINILM_MODEL, BGE_MODEL, QWEN3_MODEL, JINA_MODEL)
STABLE_MODELS = (MMINILM_MODEL, BGE_MODEL)
EXPERIMENTAL_MODELS = (QWEN3_MODEL, JINA_MODEL)

_MODEL_ALIASES = {
    "mMiniLM": MMINILM_MODEL,
    "mmarco-mMiniLM": MMINILM_MODEL,
    "BGE": BGE_MODEL,
    "bge": BGE_MODEL,
    "Qwen3": QWEN3_MODEL,
    "qwen3": QWEN3_MODEL,
    "Jina": JINA_MODEL,
    "jina": JINA_MODEL,
}


class RerankerError(Exception):
    """Base class for structured reranker errors."""

    status_code = 500
    error_type = "reranker_error"

    def __init__(self, message: str, *, model: str | None = None, root_cause: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.model = model
        self.root_cause = root_cause

    def detail(self) -> dict[str, Any]:
        detail = {"error": self.error_type, "message": self.message}
        if self.model:
            detail["model"] = self.model
        if self.root_cause:
            detail["root_cause"] = self.root_cause
        return detail


class UnsupportedRerankerModelError(RerankerError):
    status_code = 400
    error_type = "unsupported_model"

    def __init__(self, model: str) -> None:
        super().__init__(
            f"Unsupported reranker model {model!r}.",
            model=model,
        )

    def detail(self) -> dict[str, Any]:
        detail = super().detail()
        detail["supported_models"] = list(SUPPORTED_MODELS)
        return detail


class ExperimentalRerankerDisabledError(RerankerError):
    status_code = 400
    error_type = "experimental_model_disabled"

    def __init__(self, model: str) -> None:
        super().__init__(
            f"Experimental reranker model {model!r} is disabled. Set RERANKER_ALLOW_EXPERIMENTAL=true to enable it.",
            model=model,
        )


class TrustRemoteCodeDisabledError(RerankerError):
    status_code = 400
    error_type = "trust_remote_code_disabled"

    def __init__(self, model: str) -> None:
        super().__init__(
            f"Model {model!r} requires trust_remote_code. Set ALLOW_TRUST_REMOTE_CODE=true to enable it.",
            model=model,
        )


class RerankerModelLoadError(RerankerError):
    status_code = 503
    error_type = "model_load_failed"

    def __init__(self, model: str, root_cause: str) -> None:
        super().__init__(f"Failed to load reranker model {model!r}.", model=model, root_cause=root_cause)


class RerankerInferenceError(RerankerError):
    status_code = 503
    error_type = "model_inference_failed"

    def __init__(self, model: str, root_cause: str) -> None:
        super().__init__(f"Reranker model {model!r} failed during inference.", model=model, root_cause=root_cause)


@dataclass(frozen=True)
class RerankItem:
    index: int
    score: float
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"index": self.index, "score": self.score, "text": self.text}


class RerankerAdapter(ABC):
    model_name: str

    @abstractmethod
    def rerank(self, query: str, documents: list[str], top_k: int | None = None) -> list[dict[str, Any]]:
        """Return ranked items containing at least index, score and text."""


class CrossEncoderAdapter(RerankerAdapter):
    def __init__(self, model_name: str, *, device: str, max_length: int, batch_size: int) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        try:
            from sentence_transformers import CrossEncoder

            kwargs: dict[str, Any] = {"max_length": max_length}
            if device != "auto":
                kwargs["device"] = device
            self.model = CrossEncoder(model_name, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised with mocks in tests
            raise RerankerModelLoadError(model_name, _root_cause(exc)) from exc

    def rerank(self, query: str, documents: list[str], top_k: int | None = None) -> list[dict[str, Any]]:
        try:
            scores = self.model.predict(
                [(query, text) for text in documents],
                batch_size=self.batch_size,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise RerankerInferenceError(self.model_name, _root_cause(exc)) from exc
        return _ranked_items(documents, scores, top_k)


class Qwen3RerankerAdapter(CrossEncoderAdapter):
    """Official Qwen3 reranker path via sentence-transformers CrossEncoder.

    The adapter fails fast if Transformers logs the known randomly-initialized
    score.weight warning or if a tiny self-test produces invalid scores.
    """

    def __init__(self, model_name: str, *, device: str, max_length: int, batch_size: int) -> None:
        with _capture_transformers_warnings() as warnings:
            super().__init__(model_name, device=device, max_length=max_length, batch_size=batch_size)
        _raise_if_qwen_score_head_random(model_name, warnings)
        self._self_test()

    def _self_test(self) -> None:
        items = self.rerank("capital of China", ["Beijing is the capital of China.", "A banana is a fruit."], top_k=2)
        if len(items) != 2 or any(not math.isfinite(float(item["score"])) for item in items):
            raise RerankerModelLoadError(self.model_name, "Startup self-test produced invalid scores.")


class JinaRerankerAdapter(RerankerAdapter):
    def __init__(self, model_name: str, *, device: str, max_length: int, trust_remote_code: bool) -> None:
        if not trust_remote_code:
            raise TrustRemoteCodeDisabledError(model_name)
        self.model_name = model_name
        self.max_length = max_length
        try:
            from transformers import AutoModelForSequenceClassification

            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                torch_dtype="auto",
                trust_remote_code=True,
                use_flash_attn=False,
            )
            if device != "auto":
                self.model.to(device)
            self.model.eval()
        except Exception as exc:  # pragma: no cover - exercised with mocks in tests
            raise RerankerModelLoadError(model_name, _root_cause(exc)) from exc

    def rerank(self, query: str, documents: list[str], top_k: int | None = None) -> list[dict[str, Any]]:
        try:
            if hasattr(self.model, "rerank"):
                raw = self.model.rerank(query, documents, max_query_length=512, max_length=self.max_length, top_n=top_k)
                return _normalize_jina_rerank(raw, documents, top_k)
            if not hasattr(self.model, "compute_score"):
                raise TypeError("Jina model does not expose rerank() or compute_score().")
            scores = self.model.compute_score([[query, text] for text in documents], max_length=self.max_length)
        except Exception as exc:
            raise RerankerInferenceError(self.model_name, _root_cause(exc)) from exc
        return _ranked_items(documents, scores, top_k)


class RerankerRegistry:
    def __init__(
        self,
        *,
        default_model: str,
        device: str,
        batch_size: int,
        max_length: int,
        cache_size: int,
        allow_experimental: bool,
        trust_remote_code: bool,
        factories: dict[str, Callable[[], RerankerAdapter]] | None = None,
    ) -> None:
        self.default_model = normalize_model_name(default_model)
        self.device = _normalize_device(device)
        self.batch_size = batch_size
        self.max_length = max_length
        self.cache_size = cache_size
        self.allow_experimental = allow_experimental
        self.trust_remote_code = trust_remote_code
        self._cache: OrderedDict[str, RerankerAdapter] = OrderedDict()
        self._factories = factories or {}
        if self.cache_size < 1:
            raise ValueError("RERANKER_MODEL_CACHE_SIZE must be positive")
        if self.batch_size < 1:
            raise ValueError("RERANKER_BATCH_SIZE must be positive")

    @classmethod
    def from_env(cls) -> "RerankerRegistry":
        default = os.environ.get("RERANKER_DEFAULT_MODEL") or os.environ.get("RERANKER_MODEL") or MMINILM_MODEL
        return cls(
            default_model=default,
            device=os.environ.get("RERANKER_DEVICE", "auto"),
            batch_size=int(os.environ.get("RERANKER_BATCH_SIZE", "2")),
            max_length=int(os.environ.get("RERANKER_MAX_LENGTH", "512")),
            cache_size=int(os.environ.get("RERANKER_MODEL_CACHE_SIZE", "2")),
            allow_experimental=_env_bool("RERANKER_ALLOW_EXPERIMENTAL", False),
            trust_remote_code=_env_bool("ALLOW_TRUST_REMOTE_CODE", False),
        )

    @property
    def loaded_models(self) -> list[str]:
        return list(self._cache.keys())

    def get(self, model_name: str | None = None) -> RerankerAdapter:
        model = normalize_model_name(model_name or self.default_model)
        self._validate_model(model)
        cached = self._cache.get(model)
        if cached is not None:
            self._cache.move_to_end(model)
            return cached
        adapter = self._build(model)
        self._cache[model] = adapter
        self._cache.move_to_end(model)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return adapter

    def _validate_model(self, model: str) -> None:
        if model not in SUPPORTED_MODELS:
            raise UnsupportedRerankerModelError(model)
        if model in EXPERIMENTAL_MODELS and not self.allow_experimental:
            raise ExperimentalRerankerDisabledError(model)

    def _build(self, model: str) -> RerankerAdapter:
        factory = self._factories.get(model)
        if factory is not None:
            return factory()
        if model in STABLE_MODELS:
            return CrossEncoderAdapter(model, device=self.device, max_length=self.max_length, batch_size=self.batch_size)
        if model == QWEN3_MODEL:
            return Qwen3RerankerAdapter(model, device=self.device, max_length=self.max_length, batch_size=self.batch_size)
        if model == JINA_MODEL:
            return JinaRerankerAdapter(
                model,
                device=self.device,
                max_length=max(self.max_length, 1024),
                trust_remote_code=self.trust_remote_code,
            )
        raise UnsupportedRerankerModelError(model)


def normalize_model_name(value: str) -> str:
    model = (value or "").strip()
    return _MODEL_ALIASES.get(model, model)


def _ranked_items(documents: list[str], scores: Iterable[Any], top_k: int | None) -> list[dict[str, Any]]:
    values = [float(score) for score in scores]
    if len(values) != len(documents) or not all(math.isfinite(score) for score in values):
        raise ValueError("Reranker produced invalid scores.")
    items = [RerankItem(index=index, score=score, text=documents[index]) for index, score in enumerate(values)]
    items.sort(key=lambda item: item.score, reverse=True)
    if top_k is not None:
        items = items[:top_k]
    return [item.as_dict() for item in items]


def _normalize_jina_rerank(raw: Any, documents: list[str], top_k: int | None) -> list[dict[str, Any]]:
    output = []
    for item in raw or []:
        index = item.get("index", item.get("corpus_id")) if isinstance(item, dict) else getattr(item, "index", None)
        score = item.get("score") if isinstance(item, dict) else getattr(item, "score", None)
        text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
        if index is None or score is None:
            continue
        index = int(index)
        output.append({"index": index, "score": float(score), "text": str(text if text is not None else documents[index])})
    if len(output) == 0 and documents:
        raise ValueError("Jina rerank() returned no usable results.")
    if any(not math.isfinite(float(item["score"])) for item in output):
        raise ValueError("Jina rerank() returned non-finite scores.")
    output.sort(key=lambda item: float(item["score"]), reverse=True)
    return output[:top_k] if top_k is not None else output


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_device(value: str) -> str:
    value = (value or "auto").strip().lower()
    if value in {"", "auto"}:
        return "auto"
    if value in {"cpu", "cuda"} or value.startswith("cuda:"):
        return value
    return value


class _capture_transformers_warnings:
    def __init__(self) -> None:
        self.records: list[str] = []
        self._handler: logging.Handler | None = None
        self._loggers: list[logging.Logger] = []

    def __enter__(self) -> list[str]:
        outer = self

        class Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                outer.records.append(record.getMessage())

        self._handler = Handler()
        for name in ("transformers", "sentence_transformers"):
            logger = logging.getLogger(name)
            logger.addHandler(self._handler)
            self._loggers.append(logger)
        return self.records

    def __exit__(self, *args: Any) -> None:
        if self._handler is None:
            return
        for logger in self._loggers:
            logger.removeHandler(self._handler)


def _raise_if_qwen_score_head_random(model: str, warnings: list[str]) -> None:
    joined = "\n".join(warnings).lower()
    if "score.weight" in joined and "not initialized" in joined:
        raise RerankerModelLoadError(
            model,
            "Model loader reported randomly initialized score.weight. Refusing to serve random reranker scores.",
        )


def _root_cause(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


__all__ = [
    "BGE_MODEL",
    "EXPERIMENTAL_MODELS",
    "JINA_MODEL",
    "MMINILM_MODEL",
    "QWEN3_MODEL",
    "SUPPORTED_MODELS",
    "CrossEncoderAdapter",
    "ExperimentalRerankerDisabledError",
    "JinaRerankerAdapter",
    "Qwen3RerankerAdapter",
    "RerankerAdapter",
    "RerankerError",
    "RerankerInferenceError",
    "RerankerModelLoadError",
    "RerankerRegistry",
    "TrustRemoteCodeDisabledError",
    "UnsupportedRerankerModelError",
    "normalize_model_name",
]
