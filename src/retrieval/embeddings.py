from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from typing import Iterable

from .io_utils import clean_text


class Embedder(ABC):
    model_name: str
    dimension: int

    @abstractmethod
    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def l2_normalize(vector: Iterable[float]) -> list[float]:
    values = [float(v) for v in vector]
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        return values
    return [v / norm for v in values]


class SentenceTransformerEmbedder(Embedder):
    """Production embedder using sentence-transformers.

    Loads the model eagerly in ``__init__`` (~2–3 GB for e5-large). Prefer
    :class:`LazySentenceTransformerEmbedder` in notebooks / Colab when you want
    FAISS + graph to load first and defer the torch model until the first query.
    """

    def __init__(
        self,
        model_name: str,
        query_prefix: str = "query: ",
        passage_prefix: str = "passage: ",
        device: str | None = None,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for SentenceTransformerEmbedder. "
                "Install it before running the production embedding job."
            ) from exc

        self.model_name = model_name
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.device = device
        self.model = SentenceTransformer(model_name, device=device)
        dim = self.model.get_sentence_embedding_dimension()
        if not dim:
            raise RuntimeError(f"Could not determine embedding dimension for {model_name}")
        self.dimension = int(dim)

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [self.passage_prefix + text for text in texts]
        vectors = self.model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return [l2_normalize(row) for row in vectors.tolist()]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        prefixed = [self.query_prefix + text for text in texts]
        vectors = self.model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return [l2_normalize(row) for row in vectors.tolist()]


class LazySentenceTransformerEmbedder(Embedder):
    """Defer SentenceTransformer load until the first encode call.

    Keeps notebook startup light: FAISS / graph can load first; the ~2–3 GB
    e5-large model materializes only when a query is embedded. Thread-unsafe
    by design (single Colab kernel).
    """

    # Known dims for common models so VectorIndexConfig wiring works pre-load.
    _KNOWN_DIMS: dict[str, int] = {
        "intfloat/multilingual-e5-large": 1024,
        "intfloat/multilingual-e5-base": 768,
        "intfloat/multilingual-e5-small": 384,
        "intfloat/e5-large-v2": 1024,
        "intfloat/e5-base-v2": 768,
        "intfloat/e5-small-v2": 384,
    }

    def __init__(
        self,
        model_name: str,
        query_prefix: str = "query: ",
        passage_prefix: str = "passage: ",
        device: str | None = None,
        *,
        expected_dimension: int | None = None,
    ) -> None:
        self.model_name = model_name
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.device = device
        self._inner: SentenceTransformerEmbedder | None = None
        if expected_dimension is not None:
            self.dimension = int(expected_dimension)
        elif model_name in self._KNOWN_DIMS:
            self.dimension = self._KNOWN_DIMS[model_name]
        else:
            # Last resort: load once to discover dim (defeats laziness for unknown models).
            self._ensure_loaded()
            self.dimension = self._inner.dimension  # type: ignore[union-attr]

    @property
    def is_loaded(self) -> bool:
        return self._inner is not None

    def _ensure_loaded(self) -> SentenceTransformerEmbedder:
        if self._inner is None:
            self._inner = SentenceTransformerEmbedder(
                self.model_name,
                query_prefix=self.query_prefix,
                passage_prefix=self.passage_prefix,
                device=self.device,
            )
            self.dimension = self._inner.dimension
        return self._inner

    def load(self) -> "LazySentenceTransformerEmbedder":
        """Eagerly load the underlying model (optional warm-up)."""
        self._ensure_loaded()
        return self

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return self._ensure_loaded().encode_passages(texts)

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return self._ensure_loaded().encode_queries(texts)


class HashingEmbedder(Embedder):
    """Deterministic lightweight embedder for smoke tests and local development."""

    def __init__(self, dimension: int = 384) -> None:
        self.model_name = f"hashing-dev-{dimension}"
        self.dimension = dimension

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    def _encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in clean_text(text).lower().split():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        return l2_normalize(vector)
