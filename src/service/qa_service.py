"""Reusable single-question service for the local UI and other Python callers."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from evaluation.e2e_runner import (
    LATENCY_STAGES,
    GeneratorFunction,
    records_from_rows,
    run_e2e_evaluation,
    sanitize_error_text,
)
from evaluation.metrics import is_unanswerable_text
from generation.reasoning_client import RawGenerationResponse, parse_generation_response
from generation.prompt_strategy import INSUFFICIENT_CONTEXT_ANSWER, prompt_template_hash
from generation.citations import (
    CITATION_CONTRACT_VERSION, CitationReference, CitationSource, citation_contract_hash,
    PRODUCTION_EVIDENCE_CAPABILITY, evidence_diagnostics, prepare_citation_sources,
    validate_answer_citations,
)
from scripts.run_ablation_config import (
    AGENT_ABLATION_CONFIG_NAMES,
    DEFAULT_CONFIG_FILE,
    LLM_ABLATION_CONFIG_NAMES,
    PROJECT_ROOT,
    AblationConfigError,
    UnsupportedComponentError,
    build_ablation_stack,
    build_case_executor,
    load_ablation_configs,
    resolve_ablation_config,
    resolve_runtime_config,
    validate_ablation_config,
)


TOP_K_MIN = 1
TOP_K_MAX = 50
FILTER_PROFILES = ("current_law", "broad", "historical")
INTERACTIVE_CONFIG_NAMES = frozenset((*LLM_ABLATION_CONFIG_NAMES, *AGENT_ABLATION_CONFIG_NAMES))


class UIConfigError(ValueError):
    """An invalid interactive override or UI request."""


@dataclass(frozen=True)
class QuestionRequest:
    question: str
    config_name: str
    top_k_override: int | None = None
    graph_enabled_override: bool | None = None
    reranker_enabled_override: bool | None = None
    filter_profile: str | None = None
    generation_model_override: str | None = None
    prompt_strategy_override: str | None = None
    temperature_override: float | None = None
    top_p_override: float | None = None
    max_output_tokens_override: int | None = None
    timeout_seconds_override: float | None = None
    max_retries_override: int | None = None


@dataclass(frozen=True)
class SafeError:
    stage: str
    error_type: str
    message: str
    next_step: str


@dataclass(frozen=True)
class ContextRow:
    rank: int
    score: float | None
    vector_score: float | None
    rerank_score: float | None
    document_id: str | None
    provision_id: str | None
    chunk_id: str | None
    title: str | None
    article_number: str | None
    unit_type: str | None
    path: str | None
    citation: str | None
    text: str
    preview: str
    is_mock: bool = False


@dataclass(frozen=True)
class QuestionResponse:
    status: str
    answer: str | None
    abstained: bool
    contexts: tuple[ContextRow, ...]
    latency: dict[str, float | None]
    trace: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    error: SafeError | None
    resolved_config: dict[str, Any]
    diagnostics: dict[str, Any]
    citation_sources: tuple[CitationSource, ...] = ()
    citation_references: tuple[CitationReference, ...] = ()
    citation_warnings: tuple[str, ...] = ()
    citation_metrics: dict[str, Any] = field(default_factory=dict)
    suggested_followups: tuple[str, ...] = ()
    mode: str = "production"
    question: str = ""
    is_mock: bool = False


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class PreflightResult:
    runnable: bool
    status: str
    checks: tuple[PreflightCheck, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    resolved_config: dict[str, Any]


@dataclass(frozen=True)
class ConfigOption:
    name: str
    status: str
    runnable: bool
    reason: str | None = None


@dataclass(frozen=True)
class QAResources:
    retriever: Any
    generator: GeneratorFunction
    judge: Any = None
    sensitive_values: tuple[str, ...] = ()
    case_executor: Callable[[dict[str, Any]], Any] | None = None


def load_ui_config_registry(config_file: Path = DEFAULT_CONFIG_FILE) -> dict[str, dict[str, Any]]:
    """Load the canonical config matrix through the ablation runner contract."""

    return load_ablation_configs(config_file)


def list_interactive_configs(
    registry: Mapping[str, dict[str, Any]], *, project_root: Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
) -> list[ConfigOption]:
    """Return deterministic UI-appropriate configs with honest readiness states."""

    options: list[ConfigOption] = []
    for name in sorted(key for key in registry if key in INTERACTIVE_CONFIG_NAMES):
        result = run_preflight(registry[name], config_name=name, project_root=project_root, environ=environ)
        reason = result.blockers[0] if result.blockers else (result.warnings[0] if result.warnings else None)
        options.append(ConfigOption(name=name, status=result.status, runnable=result.runnable, reason=reason))
    return options


def classify_config_availability(
    config: dict[str, Any], *, config_name: str, project_root: Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
) -> ConfigOption:
    result = run_preflight(config, config_name=config_name, project_root=project_root, environ=environ)
    reason = result.blockers[0] if result.blockers else (result.warnings[0] if result.warnings else None)
    return ConfigOption(config_name, result.status, result.runnable, reason)


def apply_safe_overrides(config: Mapping[str, Any], request: QuestionRequest) -> dict[str, Any]:
    """Apply bounded in-memory controls without mutating the source config."""

    effective = deepcopy(dict(config))
    retrieval = effective["retrieval"]
    generation = effective.setdefault("generation", {})
    if not isinstance(generation, dict):
        raise UIConfigError("Generation configuration must be a mapping.")
    if request.top_k_override is not None:
        if (
            not isinstance(request.top_k_override, int)
            or isinstance(request.top_k_override, bool)
            or not TOP_K_MIN <= request.top_k_override <= TOP_K_MAX
        ):
            raise UIConfigError(f"top-k must be an integer from {TOP_K_MIN} through {TOP_K_MAX}.")
        retrieval["top_k"] = request.top_k_override
    if request.filter_profile is not None:
        if request.filter_profile not in FILTER_PROFILES:
            raise UIConfigError(f"Unknown filter profile {request.filter_profile!r}.")
        retrieval["filter_profile"] = request.filter_profile
    graph_override = request.graph_enabled_override
    reranker_override = request.reranker_enabled_override
    if graph_override is not None or reranker_override is not None:
        graph_enabled = bool(graph_override)
        reranker_enabled = bool(reranker_override)
        if graph_enabled or reranker_enabled:
            if not (graph_enabled and reranker_enabled):
                raise UIConfigError("Graph and reranker must be enabled together for the supported RRF stack.")
            _enable_graph_rrf_stack(retrieval)
        else:
            for field_name in ("graph", "fusion", "reranker"):
                section = retrieval.get(field_name)
                if isinstance(section, dict):
                    section["enabled"] = False
    if request.generation_model_override is not None:
        model = request.generation_model_override.strip()
        if not model or len(model) > 160:
            raise UIConfigError("Generation model must be a non-empty string up to 160 characters.")
        generation["model"] = model
    if request.prompt_strategy_override is not None:
        strategy = request.prompt_strategy_override.strip()
        if strategy not in {"base", "reasoning"}:
            raise UIConfigError("Prompt strategy must be either 'base' or 'reasoning'.")
        generation["prompt_strategy"] = strategy
    if request.temperature_override is not None:
        generation["temperature"] = _bounded_float(
            request.temperature_override, "temperature", minimum=0.0, maximum=2.0,
        )
    if request.top_p_override is not None:
        generation["top_p"] = _bounded_float(
            request.top_p_override, "top-p", minimum=0.05, maximum=1.0,
        )
    if request.max_output_tokens_override is not None:
        generation["max_output_tokens"] = _bounded_int(
            request.max_output_tokens_override, "max output tokens", minimum=128, maximum=8192,
        )
    if request.timeout_seconds_override is not None:
        generation["timeout_seconds"] = _bounded_float(
            request.timeout_seconds_override, "timeout seconds", minimum=5.0, maximum=300.0,
        )
    if request.max_retries_override is not None:
        generation["max_retries"] = _bounded_int(
            request.max_retries_override, "max retries", minimum=0, maximum=5,
        )
    validate_override_compatibility(effective)
    return effective


def _bounded_float(value: Any, label: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise UIConfigError(f"{label} must be a number from {minimum:g} through {maximum:g}.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise UIConfigError(f"{label} must be a number from {minimum:g} through {maximum:g}.") from exc
    if not minimum <= result <= maximum:
        raise UIConfigError(f"{label} must be a number from {minimum:g} through {maximum:g}.")
    return result


def _bounded_int(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise UIConfigError(f"{label} must be an integer from {minimum} through {maximum}.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise UIConfigError(f"{label} must be an integer from {minimum} through {maximum}.") from exc
    if result != value and not (isinstance(value, float) and value.is_integer()):
        raise UIConfigError(f"{label} must be an integer from {minimum} through {maximum}.")
    if not minimum <= result <= maximum:
        raise UIConfigError(f"{label} must be an integer from {minimum} through {maximum}.")
    return result


def validate_override_compatibility(config: Mapping[str, Any]) -> None:
    retrieval = config.get("retrieval")
    if not isinstance(retrieval, Mapping):
        raise UIConfigError("Retrieval configuration is missing.")
    dense = retrieval.get("dense")
    graph = retrieval.get("graph")
    fusion = retrieval.get("fusion")
    reranker = retrieval.get("reranker")
    flags = tuple(
        bool(section.get("enabled"))
        for section in (graph, fusion, reranker)
        if isinstance(section, Mapping)
    )
    if any(flags):
        if not isinstance(dense, Mapping) or dense.get("backend") != "faiss":
            raise UIConfigError("Graph-RRF requires the FAISS dense retriever.")
        if not all(flags):
            raise UIConfigError("Graph, RRF fusion, and reranker must be enabled together.")


def _enable_graph_rrf_stack(retrieval: dict[str, Any]) -> None:
    graph = retrieval.setdefault("graph", {})
    fusion = retrieval.setdefault("fusion", {})
    reranker = retrieval.setdefault("reranker", {})
    if not isinstance(graph, dict) or not isinstance(fusion, dict) or not isinstance(reranker, dict):
        raise UIConfigError("Graph-RRF stack sections must be mappings.")
    graph.update({
        "enabled": True,
        "backend": graph.get("backend") or "structural_pickle",
        "path": graph.get("path") or "data/graph/knowledge_graph.gpickle",
        "version": graph.get("version") or "local-knowledge-graph",
        "max_hop": graph.get("max_hop", 2),
        "max_context": graph.get("max_context", 30),
    })
    fusion.update({
        "enabled": True,
        "strategy": fusion.get("strategy") or "rrf",
        "rrf_k": fusion.get("rrf_k", 60),
    })
    reranker.update({
        "enabled": True,
        "backend": reranker.get("backend") or "cross_encoder",
        "scope": reranker.get("scope") or "global",
        "model": reranker.get("model") or "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "candidate_limit": reranker.get("candidate_limit", 30),
    })


def run_preflight(
    config: dict[str, Any], *, config_name: str = "<config>", project_root: Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
    package_available: Callable[[str], bool] | None = None,
) -> PreflightResult:
    """Evaluate structural and runtime readiness without loading models or indexes."""

    env = os.environ if environ is None else environ
    has_package = package_available or _package_available
    checks: list[PreflightCheck] = []
    warnings: list[str] = []
    blockers: list[str] = []
    resolved = deepcopy(config)

    try:
        validate_ablation_config(resolved, config_name=config_name)
        checks.append(PreflightCheck("config_schema", "ready", "Configuration is structurally valid."))
    except Exception as exc:
        message = sanitize_error_text(exc)
        blockers.append(message)
        checks.append(PreflightCheck("config_schema", "blocked", message))
        return PreflightResult(False, "runtime-blocked", tuple(checks), (), tuple(blockers), _safe_config(resolved))

    agent = resolved.get("agent", {})
    mode = agent.get("mode") or ("none" if not agent.get("enabled") else agent.get("type"))
    if mode == "plain_rag":
        mode = "none"
    if mode == "multi_tool" or agent.get("implementation_status") == "deferred":
        reason = str(agent.get("reason") or "MultiTool orchestration is deferred.")
        checks.append(PreflightCheck("agent", "deferred", reason))
        return PreflightResult(False, "deferred", tuple(checks), (), (reason,), _safe_config(resolved))

    try:
        resolved = _resolve_runtime_config_with_env(resolved, env)
        checks.append(PreflightCheck("model_selector", "ready", "Generation model selector is resolved."))
    except AblationConfigError as exc:
        message = sanitize_error_text(exc)
        blockers.append(message)
        checks.append(PreflightCheck("model_selector", "blocked", message))

    generation = resolved.get("generation", {})
    provider = generation.get("provider")
    if provider != "reference":
        key_env = str(generation.get("api_key_env") or ("GEMINI_API_KEY" if provider == "gemini" else "LLM_API_KEY"))
        if env.get(key_env):
            checks.append(PreflightCheck("generation_api_key", "ready", f"{key_env}: configured."))
        else:
            message = f"{key_env}: missing. Configure it before asking a live question."
            blockers.append(message)
            checks.append(PreflightCheck("generation_api_key", "blocked", message))
    if provider == "openai_compatible":
        base_env = str(generation.get("base_url_env") or "LLM_BASE_URL")
        if env.get(base_env):
            checks.append(PreflightCheck("provider_base_url", "ready", f"{base_env}: configured."))
        else:
            message = f"{base_env}: missing. Configure the OpenAI-compatible endpoint."
            blockers.append(message)
            checks.append(PreflightCheck("provider_base_url", "blocked", message))
        _check_package("openai", "openai", has_package, checks, blockers)
    elif provider == "gemini":
        _check_package("google.genai", "google-genai", has_package, checks, blockers)

    retrieval = resolved.get("retrieval", {})
    dense = retrieval.get("dense", {})
    backend = dense.get("backend") if dense.get("enabled") else None
    if backend == "faiss" or (backend == "bm25" and dense.get("payload_store", "faiss") == "faiss"):
        index_dir = _resolve_path(dense.get("index_path", "data/faiss_index"), project_root)
        for filename in ("index.faiss", "payloads.jsonl"):
            path = index_dir / filename
            if path.is_file():
                checks.append(PreflightCheck(f"faiss_{filename}", "ready", f"{_display_path(path, project_root)} is available."))
            else:
                message = f"Missing FAISS artifact: {_display_path(path, project_root)}."
                blockers.append(message)
                checks.append(PreflightCheck(f"faiss_{filename}", "blocked", message))
        _check_package("faiss", "faiss-cpu", has_package, checks, blockers)
        if backend == "faiss":
            _check_package("sentence_transformers", "sentence-transformers", has_package, checks, blockers)
    elif backend == "qdrant":
        _check_package("qdrant_client", "qdrant-client", has_package, checks, blockers)

    if backend == "bm25":
        service_url_env = str(dense.get("service_url_env") or "BM25_SERVICE_URL")
        if env.get(service_url_env):
            checks.append(PreflightCheck("bm25_service_url", "ready", f"{service_url_env}: configured."))
        else:
            message = f"{service_url_env}: missing. Configure it after the BM25 server is started."
            blockers.append(message)
            checks.append(PreflightCheck("bm25_service_url", "blocked", message))
        api_key_env = str(dense.get("api_key_env") or "BM25_API_KEY")
        checks.append(
            PreflightCheck(
                "bm25_api_key",
                "ready" if env.get(api_key_env) else "not_required",
                f"{api_key_env}: {'configured' if env.get(api_key_env) else 'optional and missing'}.",
            )
        )

    graph = retrieval.get("graph", {})
    fusion = retrieval.get("fusion", {})
    reranker = retrieval.get("reranker", {})
    sparse = retrieval.get("sparse", {})
    graph_rrf_flags = tuple(
        bool(section.get("enabled"))
        for section in (graph, fusion, reranker)
        if isinstance(section, Mapping)
    )
    if any(graph_rrf_flags) and not all(graph_rrf_flags):
        message = "Dense+Graph+RRF+Global-Reranker must be enabled as one complete stack."
        blockers.append(message)
        checks.append(PreflightCheck("graph_rrf_stack", "blocked", message))
    elif graph_rrf_flags and all(graph_rrf_flags):
        graph_path = _resolve_path(graph.get("path"), project_root) if graph.get("path") else None
        if graph_path is not None and graph_path.is_file():
            checks.append(PreflightCheck("graph", "ready", f"{_display_path(graph_path, project_root)} is available."))
        else:
            message = "Knowledge-graph pickle is missing."
            blockers.append(message)
            checks.append(PreflightCheck("graph", "blocked", message))
        checks.append(PreflightCheck("fusion", "ready", "RRF fusion is configured."))
        if backend != "faiss":
            _check_package("sentence_transformers", "sentence-transformers", has_package, checks, blockers)
        checks.append(PreflightCheck("reranker", "ready", "Global Cross-Encoder reranking is configured."))
        reranker_model = str(reranker.get("model") or "")
        if env.get("HF_HUB_OFFLINE") == "1" and reranker_model and not _hf_model_likely_cached(reranker_model):
            message = (
                f"Reranker model {reranker_model!r} is not cached while HF_HUB_OFFLINE=1. "
                "Temporarily set HF_HUB_OFFLINE=0 for the first model download, then clear the resource cache."
            )
            blockers.append(message)
            checks.append(PreflightCheck("reranker_model_cache", "blocked", message))
        elif reranker_model:
            checks.append(PreflightCheck("reranker_model_cache", "ready", "Reranker model cache/network setting is usable."))
    if isinstance(sparse, Mapping) and sparse.get("enabled"):
        message = "Sparse/BM25 must remain disabled for the Dense+Graph+RRF pipeline."
        blockers.append(message)
        checks.append(PreflightCheck("sparse", "blocked", message))

    for identity in ("benchmark", "corpus"):
        value = resolved.get(identity, {}).get("path")
        identity_path = _resolve_path(value, project_root) if value else None
        if identity_path is not None and identity_path.exists():
            checks.append(PreflightCheck(identity, "ready", f"{identity.capitalize()} identity path is available."))
        else:
            message = f"{identity.capitalize()} path is unavailable; it is not required for a single interactive question."
            warnings.append(message)
            checks.append(PreflightCheck(identity, "warning", message))

    if os.access(tempfile.gettempdir(), os.W_OK):
        checks.append(PreflightCheck("temporary_directory", "ready", "Temporary directory is writable."))
    else:
        message = "The process temporary directory is not writable."
        blockers.append(message)
        checks.append(PreflightCheck("temporary_directory", "blocked", message))

    status = "runtime-ready" if not blockers else "runtime-blocked"
    return PreflightResult(not blockers, status, tuple(checks), tuple(warnings), tuple(blockers), _safe_config(resolved))


def build_question_resources(
    resolved_config: dict[str, Any], *, project_root: Path = PROJECT_ROOT,
) -> QAResources:
    """Lazily construct the production stack without creating evaluation artifacts."""

    retriever, generator, judge, secrets = build_ablation_stack(resolved_config, project_root=project_root)
    executor = build_case_executor(
        resolved_config, retriever=retriever, generator=generator, sensitive_values=secrets
    )
    return QAResources(retriever, generator, judge, tuple(value for value in secrets if value), executor)


def answer_question(
    request: QuestionRequest, *, config_file: Path = DEFAULT_CONFIG_FILE, project_root: Path = PROJECT_ROOT,
    registry: Mapping[str, dict[str, Any]] | None = None, resources: QAResources | None = None,
    environ: Mapping[str, str] | None = None,
) -> QuestionResponse:
    """Execute one question through the production E2E core without writing a run directory."""

    question = request.question.strip() if isinstance(request.question, str) else ""
    if not question:
        return _error_response(
            status="failed", stage="validation", error_type="ValidationError",
            message="Question must not be empty.", next_step="Enter a question and press Ask.",
        )
    try:
        configs = dict(registry) if registry is not None else load_ui_config_registry(config_file)
        source = resolve_ablation_config(configs, request.config_name)
        effective = apply_safe_overrides(source, request)
        preflight = run_preflight(
            effective, config_name=request.config_name, project_root=project_root, environ=environ
        )
        diagnostics = build_diagnostics(request.config_name, preflight.resolved_config, preflight)
        if preflight.status == "deferred":
            return QuestionResponse(
                "deferred", None, False, (), {}, (), preflight.warnings,
                SafeError("preflight", "DeferredConfiguration", preflight.blockers[0], "Select an implemented config."),
                preflight.resolved_config, diagnostics,
            )
        if not preflight.runnable:
            return QuestionResponse(
                "blocked", None, False, (), {}, (), preflight.warnings,
                SafeError("preflight", "RuntimeBlocked", "; ".join(preflight.blockers), "Resolve the listed readiness blockers."),
                preflight.resolved_config, diagnostics,
            )
        runtime_config = _resolve_runtime_config_with_env(effective, os.environ if environ is None else environ)
        active = resources or build_question_resources(runtime_config, project_root=project_root)
        executor = active.case_executor
        if executor is None:
            executor = build_case_executor(
                runtime_config, retriever=active.retriever, generator=active.generator,
                sensitive_values=active.sensitive_values,
            )

        def safe_generator(row: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
            if not chunks:
                return ""
            return active.generator(row, context, chunks)

        # A supplied executor already owns its generator; production-built resources use the same generator.
        started = time.perf_counter()
        result = run_e2e_evaluation(
            records_from_rows([{"qa_id": "interactive", "question": question, "answer_type": ""}]),
            retriever=active.retriever,
            generator=safe_generator,
            retrieval_top_k=int(runtime_config["retrieval"]["top_k"]),
            filter_profile=str(runtime_config["retrieval"].get("filter_profile") or "broad"),
            judge=active.judge,
            config=runtime_config,
            sensitive_values=active.sensitive_values,
            case_executor=executor,
        )
        prediction = result.predictions[0]
        latency = dict(prediction.get("latency_ms") or {})
        latency.setdefault("total", round((time.perf_counter() - started) * 1000.0, 6))
        contexts = tuple(normalize_context_rows(prediction.get("retrieved_context") or []))
        trace = tuple(normalize_trace_rows(prediction.get("agent_trace") or []))
        if prediction.get("status") == "failed":
            error = prediction.get("error") or {}
            return QuestionResponse(
                "failed", None, False, contexts, latency, trace, preflight.warnings,
                SafeError(
                    str(prediction.get("failed_stage") or "execution"), str(error.get("type") or "ExecutionError"),
                    sanitize_error_text(error.get("message") or "Question execution failed.", active.sensitive_values),
                    "Review the failed stage and readiness diagnostics, then retry.",
                ),
                _safe_config(runtime_config), diagnostics,
            )
        raw_answer = str(prediction.get("predicted_answer") or "").strip()
        answer = parse_generation_response(RawGenerationResponse(raw_answer, None)).answer.strip() or None
        abstained = (
            prediction.get("status") == "skipped"
            or not contexts
            or bool(answer and (
                answer.strip() == INSUFFICIENT_CONTEXT_ANSWER
                or is_unanswerable_text(answer)
            ))
        )
        if abstained:
            answer = None
        elif not answer:
            return QuestionResponse(
                "failed", None, False, contexts, latency, trace, preflight.warnings,
                SafeError("generation", "MalformedGenerationResponse", "The generator returned no final answer.",
                          "Check provider compatibility and response formatting."),
                _safe_config(runtime_config), diagnostics,
            )
        citation_sources = prepare_citation_sources(prediction.get("retrieved_context") or [])
        citation_result = validate_answer_citations(answer or "", citation_sources)
        answer = citation_result.answer or None
        citation_warnings = tuple(str(value) for value in prediction.get("citation_warnings") or citation_result.warnings)
        citation_metrics = dict(prediction.get("citation_metrics") or citation_result.metrics)
        diagnostics["citation_contract"] = {
            "invalid_ids": list(prediction.get("invalid_citation_ids") or citation_result.invalid_ids),
            "uncited_source_ids": list(citation_result.uncited_source_ids),
        }
        diagnostics.update(evidence_diagnostics(
            citation_result.cited_sources, capability=PRODUCTION_EVIDENCE_CAPABILITY,
        ))
        return QuestionResponse(
            "abstained" if abstained else "completed", answer, abstained, contexts, latency, trace,
            preflight.warnings, None, _safe_config(runtime_config), diagnostics,
            citation_result.cited_sources, citation_result.references, citation_warnings,
            citation_metrics, build_followup_suggestions(question, citation_result.cited_sources),
            "production", question, False,
        )
    except (AblationConfigError, UIConfigError, UnsupportedComponentError) as exc:
        return _error_response(
            status="blocked", stage="configuration", error_type=type(exc).__name__,
            message=sanitize_error_text(exc), next_step="Correct the selected config or interactive overrides.",
        )
    except Exception as exc:
        return _error_response(
            status="failed", stage="service", error_type=type(exc).__name__,
            message=sanitize_error_text(exc), next_step="Review readiness diagnostics and retry.",
        )


def normalize_context_rows(items: Sequence[Any], *, preview_chars: int = 300) -> list[ContextRow]:
    rows: list[ContextRow] = []
    for fallback_rank, item in enumerate(items, 1):
        data = item if isinstance(item, Mapping) else vars(item)
        rank_value = data.get("rank", fallback_rank)
        rank = int(rank_value) if isinstance(rank_value, (int, float)) and not isinstance(rank_value, bool) else fallback_rank
        text = str(data.get("text") or data.get("chunk_text") or "")
        citation = data.get("citation") or data.get("citation_anchor") or data.get("citation_label")
        rows.append(ContextRow(
            rank=rank, score=_optional_float(data.get("score")),
            vector_score=_optional_float(data.get("vector_score")), rerank_score=_optional_float(data.get("rerank_score")),
            document_id=_optional_text(data.get("document_id") or data.get("id_str")),
            provision_id=_optional_text(data.get("provision_id") or data.get("parent_unit_id")),
            chunk_id=_optional_text(data.get("chunk_id")), title=_optional_text(data.get("title")),
            article_number=_optional_text(data.get("article_number")), unit_type=_optional_text(data.get("unit_type")),
            path=_optional_text(data.get("path")), citation=_optional_text(citation), text=text,
            preview=text if len(text) <= preview_chars else text[: max(0, preview_chars - 1)].rstrip() + "…",
            is_mock=bool(data.get("is_mock", False)),
        ))
    return sorted(rows, key=lambda row: row.rank)


def normalize_latency_rows(latency: Mapping[str, Any]) -> list[dict[str, Any]]:
    ordered = [*LATENCY_STAGES, *(key for key in latency if key not in LATENCY_STAGES)]
    return [{"stage": stage, "latency_ms": _optional_float(latency.get(stage))} for stage in ordered]


def normalize_trace_rows(trace: Sequence[Any]) -> list[dict[str, Any]]:
    allowed = ("step", "event", "action", "reason_code", "tool", "status", "result_count", "latency_ms", "error_type")
    rows: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(trace):
        data = item if isinstance(item, Mapping) else vars(item)
        safe = {key: data.get(key) for key in allowed if data.get(key) is not None}
        step = safe.get("step")
        order = int(step) if isinstance(step, int) and not isinstance(step, bool) else 10_000 + index
        rows.append((order, index, safe))
    return [row for _, _, row in sorted(rows)]


def build_diagnostics(config_name: str, config: Mapping[str, Any], preflight: PreflightResult) -> dict[str, Any]:
    generation = config.get("generation", {})
    retrieval = config.get("retrieval", {})
    dense = retrieval.get("dense", {})
    agent = config.get("agent", {})
    return {
        "selected_config": config_name,
        "effective_top_k": retrieval.get("top_k"),
        "filter_profile": retrieval.get("filter_profile"),
        "generation_provider": generation.get("provider"),
        "generation_model": generation.get("model"),
        "prompt_strategy": generation.get("prompt_strategy") or "base",
        "prompt_template_version": generation.get("prompt_template_version"),
        "prompt_template_hash": prompt_template_hash(generation.get("prompt_strategy")),
        "citation_contract_version": CITATION_CONTRACT_VERSION,
        "citation_contract_hash": citation_contract_hash(),
        "agent_mode": agent.get("mode") or ("none" if not agent.get("enabled") else agent.get("type")),
        "retrieval_backend": dense.get("backend"),
        "index_identity": dense.get("index_version"),
        "index_path": dense.get("index_path"),
        "graph_enabled": bool(retrieval.get("graph", {}).get("enabled")),
        "reranker_enabled": bool(retrieval.get("reranker", {}).get("enabled")),
        "seed": config.get("seed"),
        "preflight_status": preflight.status,
        "preflight_checks": [vars(check) for check in preflight.checks],
    }


def format_safe_error(error: object, sensitive_values: Sequence[str] = ()) -> str:
    return sanitize_error_text(error, sensitive_values)


def build_followup_suggestions(question: str, sources: Sequence[CitationSource]) -> tuple[str, ...]:
    """Return bounded deterministic UI helpers; these are questions, not factual claims."""
    suggestions = ["What exceptions or limitations should I check?"]
    if sources:
        suggestions.append("Which retrieved source most directly supports this answer?")
        if any(source.article or source.section for source in sources):
            suggestions.append("How do the cited articles or sections relate to each other?")
    else:
        suggestions.append("How could I narrow this question to find relevant evidence?")
    return tuple(suggestions[:3])


def _error_response(*, status: str, stage: str, error_type: str, message: str, next_step: str) -> QuestionResponse:
    return QuestionResponse(status, None, False, (), {}, (), (), SafeError(stage, error_type, message, next_step), {}, {})


def _resolve_runtime_config_with_env(config: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    selectors = [
        ("generation", "model"),
        ("judge", "model"),
    ]
    copied = deepcopy(config)
    for section_name, field in selectors:
        section = copied.get(section_name)
        if not isinstance(section, dict):
            continue
        value = section.get(field)
        if isinstance(value, str) and value.startswith("env:"):
            name = value[4:]
            resolved = env.get(name, "")
            if not resolved:
                raise AblationConfigError(f"Missing model selector environment variable {name!r}.")
            section[field] = resolved
    # Use the runner's resolver too so non-overridden process environments follow one contract.
    if env is os.environ:
        return resolve_runtime_config(copied)
    return copied


def _check_package(module: str, package: str, checker: Callable[[str], bool], checks: list[PreflightCheck], blockers: list[str]) -> None:
    if checker(module):
        checks.append(PreflightCheck(f"package_{module}", "ready", f"Python package {package} is available."))
    else:
        message = f"Missing Python package {package}."
        blockers.append(message)
        checks.append(PreflightCheck(f"package_{module}", "blocked", message))


def _package_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _hf_model_likely_cached(model_name: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache  # type: ignore[import-untyped]
    except ImportError:
        return False
    required_groups = (
        ("config.json",),
        ("tokenizer.json", "tokenizer_config.json"),
        ("model.safetensors", "pytorch_model.bin"),
    )
    for filenames in required_groups:
        if not any(bool(try_to_load_from_cache(model_name, name)) for name in filenames):
            return False
    return True


def _resolve_path(value: object, project_root: Path) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else project_root / path


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _safe_config(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "***"
                if _is_sensitive_config_key(str(key))
                else _safe_config(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_config(item) for item in value]
    return value


def _is_sensitive_config_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_env"):
        return False
    sensitive_exact = {
        "api_key",
        "apikey",
        "authorization",
        "auth_header",
        "bearer_token",
        "access_token",
        "refresh_token",
        "secret",
        "client_secret",
        "password",
        "credential",
    }
    if lowered in sensitive_exact:
        return True
    return (
        lowered.endswith("_api_key")
        or lowered.endswith("_secret")
        or lowered.endswith("_password")
        or lowered.endswith("_credential")
    )


def _optional_text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


__all__ = [
    "ConfigOption", "ContextRow", "FILTER_PROFILES", "PreflightCheck", "PreflightResult",
    "QAResources", "QuestionRequest", "QuestionResponse", "SafeError", "TOP_K_MAX", "TOP_K_MIN",
    "UIConfigError", "answer_question", "apply_safe_overrides", "build_diagnostics", "build_followup_suggestions",
    "build_question_resources", "classify_config_availability", "format_safe_error",
    "list_interactive_configs", "load_ui_config_registry", "normalize_context_rows",
    "normalize_latency_rows", "normalize_trace_rows", "run_preflight", "validate_override_compatibility",
]
