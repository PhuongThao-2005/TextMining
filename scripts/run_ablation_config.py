#!/usr/bin/env python3
"""Run one named ablation configuration and persist a complete run contract."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.e2e_runner import (  # noqa: E402
    E2ERunResult,
    GeneratorFunction,
    JudgeFunction,
    read_benchmark_records,
    run_e2e_evaluation,
    write_e2e_artifacts,
)
from agent.contracts import (  # noqa: E402
    AGENT_VERSION,
    TRACE_SCHEMA_VERSION,
    TOOL_CONTRACT_VERSION,
    AgentMode,
    coerce_agent_mode,
)
from agent.simple_planner import PLANNER_POLICY, PLANNER_POLICY_VERSION, SimplePlanner  # noqa: E402
from agent.tools import RetrievalTool  # noqa: E402
from evaluation.io_utils import write_json  # noqa: E402
from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever  # noqa: E402
from knowledge_graph import GraphExpansion, load_knowledge_graph  # noqa: E402
from retrieval import GraphRRFGlobalReranker, VectorRetriever  # noqa: E402
from generation.prompt_strategy import (  # noqa: E402
    PROMPT_TEMPLATE_VERSION,
    build_generation_prompt,
    coerce_prompt_strategy,
    prompt_template_hash,
)
from generation.citations import CITATION_CONTRACT_VERSION, citation_contract_hash  # noqa: E402
from generation.reasoning_client import (  # noqa: E402
    GeneratorClient,
    RawGenerationResponse,
    generate_answer,
    parse_generation_response,
)


DEFAULT_CONFIG_FILE = PROJECT_ROOT / "configs" / "ablation_configs.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "evaluation_runs" / "ablation"
SUPPORTED_DENSE_BACKENDS = {"faiss", "qdrant", "hashing", "bm25"}
SUPPORTED_GENERATORS = {"reference", "gemini", "openai_compatible"}
SUPPORTED_JUDGES = {"none", "gemini"}
RUN_STATUSES = {"completed", "failed", "skipped", "deferred", "needs-rerun"}
LLM_ABLATION_CONFIG_NAMES = (
    "LLM-BaseReasoning",
    "LLM-CoTReasoning",
    "LLM-LargerModel",
    "LLM-LargerModel-CoTReasoning",
)
AGENT_ABLATION_CONFIG_NAMES = (
    "Agent-None-PlainRAG",
    "Agent-SimplePlanner",
    "Agent-MultiTool-Orchestrated",
)


class AblationConfigError(ValueError):
    """Configuration is invalid or cannot be resolved."""


class UnsupportedComponentError(RuntimeError):
    """A valid config requests a component not wired into the runner."""


@dataclass(frozen=True)
class AblationRunOutcome:
    config_name: str
    status: str
    run_id: str | None
    output_dir: Path | None
    artifacts: dict[str, str]
    counts: dict[str, int]
    error: str | None = None


class _UniqueKeyLoader:
    @staticmethod
    def load(text: str) -> Any:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AblationConfigError("PyYAML is required to read ablation configs. Install it with: pip install pyyaml") from exc

        class Loader(yaml.SafeLoader):
            pass

        def construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
            mapping: dict[Any, Any] = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise AblationConfigError(f"Duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}.")
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
        return yaml.load(text, Loader=Loader)


def load_ablation_configs(path: Path = DEFAULT_CONFIG_FILE) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise AblationConfigError(f"Ablation config file not found: {path}")
    payload = _UniqueKeyLoader.load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AblationConfigError("Ablation config file root must be a mapping.")
    if payload.get("schema_version") != 1:
        raise AblationConfigError("Unsupported or missing schema_version; expected integer 1.")
    configs = payload.get("configs")
    if not isinstance(configs, dict) or not configs:
        raise AblationConfigError("Config file must contain a non-empty 'configs' mapping.")
    for name, config in configs.items():
        if not isinstance(name, str) or not name.strip():
            raise AblationConfigError("Every config name must be a non-empty string.")
        if not isinstance(config, dict):
            raise AblationConfigError(f"Config {name!r} must be a mapping.")
    if all(name in configs for name in LLM_ABLATION_CONFIG_NAMES):
        validate_llm_ablation_fairness(configs)
    if all(name in configs for name in AGENT_ABLATION_CONFIG_NAMES):
        validate_agent_ablation_fairness(configs)
    return configs


def resolve_ablation_config(configs: Mapping[str, dict[str, Any]], name: str) -> dict[str, Any]:
    if name not in configs:
        available = ", ".join(configs) or "(none)"
        raise AblationConfigError(f"Unknown ablation config {name!r}. Available configs: {available}")
    return json.loads(json.dumps(configs[name]))


def validate_ablation_config(config: dict[str, Any], *, config_name: str = "<config>") -> None:
    benchmark = _require_mapping(config, "benchmark", config_name)
    corpus = _require_mapping(config, "corpus", config_name)
    retrieval = _require_mapping(config, "retrieval", config_name)
    generation = _require_mapping(config, "generation", config_name)
    agent = _require_mapping(config, "agent", config_name)
    output = _require_mapping(config, "output", config_name)

    _require_non_empty_string(benchmark, "path", f"{config_name}.benchmark")
    _require_non_empty_string(benchmark, "version", f"{config_name}.benchmark")
    _require_non_empty_string(corpus, "path", f"{config_name}.corpus")
    _require_non_empty_string(corpus, "version", f"{config_name}.corpus")
    _require_non_empty_string(output, "root", f"{config_name}.output")

    top_k = retrieval.get("top_k")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        raise AblationConfigError(f"{config_name}.retrieval.top_k must be a positive integer.")
    filter_profile = retrieval.get("filter_profile", "broad")
    if filter_profile not in {"current_law", "broad", "historical"}:
        raise AblationConfigError(
            f"{config_name}.retrieval.filter_profile must be current_law, broad, or historical."
        )

    dense = _require_mapping(retrieval, "dense", f"{config_name}.retrieval")
    _require_bool(dense, "enabled", f"{config_name}.retrieval.dense")
    if dense["enabled"]:
        backend = _require_non_empty_string(dense, "backend", f"{config_name}.retrieval.dense")
        if backend not in SUPPORTED_DENSE_BACKENDS:
            raise AblationConfigError(
                f"Unsupported dense backend {backend!r}; expected one of {sorted(SUPPORTED_DENSE_BACKENDS)}."
            )
        if backend in {"faiss", "bm25"}:
            _require_non_empty_string(dense, "index_path", f"{config_name}.retrieval.dense")
        if backend == "qdrant":
            _require_non_empty_string(dense, "collection", f"{config_name}.retrieval.dense")
        if backend == "bm25":
            _require_non_empty_string(dense, "service_url_env", f"{config_name}.retrieval.dense")
            payload_store = dense.get("payload_store", "faiss")
            if payload_store not in {"faiss", "qdrant"}:
                raise AblationConfigError(
                    f"{config_name}.retrieval.dense.payload_store must be faiss or qdrant."
                )

    enabled_retrievers = bool(dense["enabled"])
    for component in ("sparse", "graph", "fusion", "reranker"):
        section = retrieval.get(component, {"enabled": False})
        if not isinstance(section, dict):
            raise AblationConfigError(f"{config_name}.retrieval.{component} must be a mapping.")
        _require_bool(section, "enabled", f"{config_name}.retrieval.{component}")
        if component in {"sparse", "graph"}:
            enabled_retrievers = enabled_retrievers or bool(section["enabled"])
    graph_enabled = bool(retrieval.get("graph", {}).get("enabled"))
    fusion_enabled = bool(retrieval.get("fusion", {}).get("enabled"))
    reranker_enabled = bool(retrieval.get("reranker", {}).get("enabled"))
    if any((graph_enabled, fusion_enabled, reranker_enabled)):
        if not all((dense["enabled"], graph_enabled, fusion_enabled, reranker_enabled)):
            raise AblationConfigError(
                f"{config_name} must enable dense, graph, fusion, and reranker together for the supported Graph-RRF stack."
            )
        if retrieval.get("sparse", {}).get("enabled"):
            raise AblationConfigError(
                f"{config_name} Graph-RRF stack does not use sparse/BM25 retrieval."
            )
        if dense.get("backend") == "bm25":
            raise AblationConfigError(
                f"{config_name} Graph-RRF stack requires a vector Dense backend, not BM25."
            )
        graph = retrieval["graph"]
        if graph.get("backend") != "structural_pickle":
            raise AblationConfigError(
                f"{config_name}.retrieval.graph.backend must be 'structural_pickle'."
            )
        _require_non_empty_string(graph, "path", f"{config_name}.retrieval.graph")
        for field, default in (("max_hop", 2), ("max_context", 30)):
            value = graph.get(field, default)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise AblationConfigError(
                    f"{config_name}.retrieval.graph.{field} must be a positive integer."
                )
        fusion = retrieval["fusion"]
        if fusion.get("strategy") != "rrf":
            raise AblationConfigError(
                f"{config_name}.retrieval.fusion.strategy must be 'rrf'."
            )
        rrf_k = fusion.get("rrf_k", 60)
        if not isinstance(rrf_k, int) or isinstance(rrf_k, bool) or rrf_k < 1:
            raise AblationConfigError(f"{config_name}.retrieval.fusion.rrf_k must be a positive integer.")
        reranker = retrieval["reranker"]
        if reranker.get("backend") != "cross_encoder":
            raise AblationConfigError(
                f"{config_name}.retrieval.reranker.backend must be 'cross_encoder'."
            )
        _require_non_empty_string(reranker, "model", f"{config_name}.retrieval.reranker")
        if reranker.get("scope", "global") != "global":
            raise AblationConfigError(
                f"{config_name}.retrieval.reranker.scope must be 'global'."
            )
        candidate_limit = reranker.get("candidate_limit", 30)
        if not isinstance(candidate_limit, int) or isinstance(candidate_limit, bool) or candidate_limit < 1:
            raise AblationConfigError(
                f"{config_name}.retrieval.reranker.candidate_limit must be a positive integer."
            )
    if not enabled_retrievers:
        raise AblationConfigError(f"{config_name} must enable at least one retriever.")

    provider = _require_non_empty_string(generation, "provider", f"{config_name}.generation")
    if provider not in SUPPORTED_GENERATORS:
        raise AblationConfigError(
            f"Unsupported generation provider {provider!r}; expected one of {sorted(SUPPORTED_GENERATORS)}."
        )
    _require_non_empty_string(generation, "model", f"{config_name}.generation")
    try:
        coerce_prompt_strategy(generation.get("prompt_strategy"))
    except ValueError as exc:
        raise AblationConfigError(f"{config_name}.generation: {exc}") from exc
    if "prompt_template_version" in generation:
        version = _require_non_empty_string(
            generation, "prompt_template_version", f"{config_name}.generation"
        )
        if version != PROMPT_TEMPLATE_VERSION:
            raise AblationConfigError(
                f"{config_name}.generation.prompt_template_version must be "
                f"{PROMPT_TEMPLATE_VERSION!r}; got {version!r}."
            )
    _validate_number(generation, "temperature", config_name, minimum=0.0)
    _validate_number(generation, "top_p", config_name, minimum=0.0, maximum=1.0)
    _validate_number(generation, "timeout_seconds", config_name, minimum=0.0, exclusive_minimum=True)
    _validate_integer(generation, "max_output_tokens", config_name, minimum=1)
    _validate_integer(generation, "max_retries", config_name, minimum=0)

    judge = config.get("judge", {"provider": "none"})
    if not isinstance(judge, dict):
        raise AblationConfigError(f"{config_name}.judge must be a mapping.")
    judge_provider = _require_non_empty_string(judge, "provider", f"{config_name}.judge")
    if judge_provider not in SUPPORTED_JUDGES:
        raise AblationConfigError(
            f"Unsupported judge provider {judge_provider!r}; expected one of {sorted(SUPPORTED_JUDGES)}."
        )
    if judge_provider != "none":
        _require_non_empty_string(judge, "model", f"{config_name}.judge")

    _require_bool(agent, "enabled", f"{config_name}.agent")
    raw_mode = agent.get("mode", "none" if not agent["enabled"] else agent.get("type"))
    if raw_mode == "plain_rag":
        raw_mode = "none"
    try:
        mode = coerce_agent_mode(raw_mode)
    except ValueError as exc:
        raise AblationConfigError(f"{config_name}.agent: {exc}") from exc
    if mode is AgentMode.NONE and agent["enabled"]:
        raise AblationConfigError(f"{config_name}.agent.enabled must be false when mode is none.")
    if mode is AgentMode.SIMPLE_PLANNER:
        if not agent["enabled"]:
            raise AblationConfigError(f"{config_name}.agent.enabled must be true for simple_planner.")
        max_steps = agent.get("max_steps")
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= 3:
            raise AblationConfigError(f"{config_name}.agent.max_steps must be an integer from 1 through 3.")
        if agent.get("max_tool_calls") != 1:
            raise AblationConfigError(f"{config_name}.agent.max_tool_calls must equal 1.")
        if agent.get("allowed_tools") != ["retrieve"]:
            raise AblationConfigError(f"{config_name}.agent.allowed_tools must be exactly ['retrieve'].")
        deadline = agent.get("deadline_seconds")
        if not isinstance(deadline, (int, float)) or isinstance(deadline, bool) or not 0 < deadline <= 300:
            raise AblationConfigError(f"{config_name}.agent.deadline_seconds must be numeric and at most 300.")
        retries = agent.get("max_retries")
        if retries != 0:
            raise AblationConfigError(f"{config_name}.agent.max_retries must equal 0 with a one-call tool limit.")
    if mode is AgentMode.MULTI_TOOL and agent.get("implementation_status") != "deferred":
        raise AblationConfigError(f"{config_name}.agent multi_tool must declare implementation_status: deferred.")
    seed = config.get("seed", 42)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise AblationConfigError(f"{config_name}.seed must be an integer.")
    if "metadata" in config and not isinstance(config["metadata"], dict):
        raise AblationConfigError(f"{config_name}.metadata must be a mapping.")


def validate_llm_ablation_fairness(configs: Mapping[str, dict[str, Any]]) -> None:
    """Fail when the controlled LLM configs differ outside their intended variable."""

    missing = [name for name in LLM_ABLATION_CONFIG_NAMES if name not in configs]
    if missing:
        raise AblationConfigError(
            "LLM ablation fairness validation requires configs: " + ", ".join(missing)
        )
    base = configs["LLM-BaseReasoning"]
    prompt_path = ("generation", "prompt_strategy")
    model_path = ("generation", "model")
    comparisons = (
        ("LLM-CoTReasoning", {prompt_path}),
        ("LLM-LargerModel", {model_path}),
        ("LLM-LargerModel-CoTReasoning", {model_path, prompt_path}),
    )
    for other_name, allowed_paths in comparisons:
        differences = _differing_paths(base, configs[other_name])
        unintended = sorted(differences - allowed_paths)
        if unintended:
            formatted = ", ".join(".".join(path) for path in unintended)
            raise AblationConfigError(
                f"Unfair LLM ablation {other_name!r}; unintended differing fields: {formatted}."
            )
        missing_differences = sorted(allowed_paths - differences)
        if missing_differences:
            formatted = ", ".join(".".join(path) for path in missing_differences)
            raise AblationConfigError(
                f"LLM ablation {other_name!r} must differ at {formatted}."
            )


def validate_agent_ablation_fairness(configs: Mapping[str, dict[str, Any]]) -> None:
    """Ensure Plain RAG and Simple Planner differ only in their agent section."""
    missing = [name for name in AGENT_ABLATION_CONFIG_NAMES if name not in configs]
    if missing:
        raise AblationConfigError("Agent ablation fairness validation requires configs: " + ", ".join(missing))
    plain = configs["Agent-None-PlainRAG"]
    planner = configs["Agent-SimplePlanner"]
    differences = _differing_paths(plain, planner)
    unintended = sorted(path for path in differences if not path or path[0] != "agent")
    if unintended:
        formatted = ", ".join(".".join(path) for path in unintended)
        raise AblationConfigError(f"Unfair agent ablation; unintended differing fields: {formatted}.")
    if not differences:
        raise AblationConfigError("Agent ablation configs must differ in their agent section.")


def _differing_paths(
    left: Any,
    right: Any,
    prefix: tuple[str, ...] = (),
) -> set[tuple[str, ...]]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        differences: set[tuple[str, ...]] = set()
        for key in sorted(set(left) | set(right), key=str):
            path = (*prefix, str(key))
            if key not in left or key not in right:
                differences.add(path)
            else:
                differences.update(_differing_paths(left[key], right[key], path))
        return differences
    return set() if left == right else {prefix}


def validate_required_paths(config: dict[str, Any], *, project_root: Path = PROJECT_ROOT) -> None:
    required = [
        ("benchmark.path", _resolved_path(config["benchmark"]["path"], project_root)),
        ("corpus.path", _resolved_path(config["corpus"]["path"], project_root)),
    ]
    dense = config["retrieval"]["dense"]
    if dense["enabled"] and (
        dense["backend"] == "faiss"
        or (dense["backend"] == "bm25" and dense.get("payload_store", "faiss") == "faiss")
    ):
        required.append(("retrieval.dense.index_path", _resolved_path(dense["index_path"], project_root)))
    graph = config["retrieval"].get("graph", {})
    if graph.get("enabled"):
        graph_path = graph.get("path")
        if not isinstance(graph_path, str) or not graph_path:
            raise AblationConfigError("Enabled graph retrieval requires retrieval.graph.path.")
        required.append(("retrieval.graph.path", _resolved_path(graph_path, project_root)))
    sparse = config["retrieval"].get("sparse", {})
    if sparse.get("enabled") and sparse.get("index_path"):
        required.append(("retrieval.sparse.index_path", _resolved_path(sparse["index_path"], project_root)))

    missing = [f"{field}={path}" for field, path in required if not path.exists()]
    if missing:
        raise AblationConfigError("Required path validation failed: " + "; ".join(missing))


def build_ablation_stack(
    config: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
) -> tuple[Any, GeneratorFunction, JudgeFunction | None, list[str]]:
    retrieval = config["retrieval"]
    if retrieval.get("sparse", {}).get("enabled"):
        raise UnsupportedComponentError(
            "Sparse/BM25 is excluded from the supported Dense+Graph+RRF+Global-Reranker stack."
        )
    dense = retrieval["dense"]
    if not dense["enabled"]:
        raise UnsupportedComponentError("The current runner requires retrieval.dense.enabled=true.")
    backend = dense["backend"]
    payload_store = str(dense.get("payload_store") or "faiss") if backend == "bm25" else None
    runtime_store = payload_store or ("faiss" if backend in {"faiss", "hashing"} else "qdrant")
    bm25_api_key = _env_value(dense.get("api_key_env") or "BM25_API_KEY") if backend == "bm25" else None
    runtime = RetrieverRuntimeConfig(
        backend="bm25" if backend == "bm25" else "vector",
        store=runtime_store,
        index_dir=_resolved_path(dense.get("index_path", "data/faiss_index"), project_root),
        qdrant_url=str(dense.get("url") or "http://localhost:6333"),
        qdrant_api_key=_env_value(dense.get("api_key_env")),
        collection_name=str(dense.get("collection") or "legal_chunks"),
        model=str(dense.get("model") or "intfloat/multilingual-e5-large"),
        dev_hashing=backend == "hashing",
        top_k=max(int(retrieval["top_k"]) * 3, int(retrieval["top_k"])),
        top_n=int(retrieval["top_k"]),
        score_threshold=dense.get("score_threshold", 0.3),
        expand_units=bool(dense.get("expand_units", True)),
        bm25_service_url=_env_value(dense.get("service_url_env") or "BM25_SERVICE_URL"),
        bm25_api_key=bm25_api_key,
        bm25_timeout_seconds=float(dense.get("timeout_seconds", 300.0)),
    )
    retriever = build_vector_retriever(runtime)
    graph_enabled = bool(retrieval.get("graph", {}).get("enabled"))
    fusion_enabled = bool(retrieval.get("fusion", {}).get("enabled"))
    reranker_enabled = bool(retrieval.get("reranker", {}).get("enabled"))
    if any((graph_enabled, fusion_enabled, reranker_enabled)):
        if not all((graph_enabled, fusion_enabled, reranker_enabled)):
            raise UnsupportedComponentError(
                "Dense+Graph+RRF+Global-Reranker must be enabled as one complete stack."
            )
        if not isinstance(retriever, VectorRetriever):
            raise UnsupportedComponentError("Graph-RRF requires a vector-backed Dense retriever.")
        graph_config = retrieval["graph"]
        fusion_config = retrieval["fusion"]
        reranker_config = retrieval["reranker"]
        graph_path = _resolved_path(graph_config["path"], project_root)
        graph = load_knowledge_graph(graph_path).graph
        retriever = GraphRRFGlobalReranker(
            dense_retriever=retriever,
            graph_expansion=GraphExpansion(graph),
            cross_encoder_name=str(reranker_config["model"]),
            rrf_k=int(fusion_config.get("rrf_k", 60)),
            graph_max_hop=int(graph_config.get("max_hop", 2)),
            graph_max_context=int(graph_config.get("max_context", 30)),
            rerank_candidate_limit=int(reranker_config.get("candidate_limit", 30)),
        )
    generator, generator_secrets = _build_generator(config["generation"])
    judge, judge_secrets = _build_judge(config.get("judge", {"provider": "none"}))
    qdrant_key = runtime.qdrant_api_key or ""
    return retriever, generator, judge, [
        *generator_secrets,
        *judge_secrets,
        qdrant_key,
        bm25_api_key or "",
    ]


def resolve_runtime_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied config with environment-backed model selectors resolved."""

    resolved = json.loads(json.dumps(config))
    _resolve_environment_model(resolved)
    return resolved


def apply_runtime_path_overrides(
    config: Mapping[str, Any],
    *,
    benchmark_source: Path | None = None,
    corpus_source: Path | None = None,
    faiss_index_source: Path | None = None,
    faiss_payloads_source: Path | None = None,
    faiss_manifest_source: Path | None = None,
    graph_source: Path | None = None,
    runs_root: Path | None = None,
    selected_device: str | None = None,
) -> dict[str, Any]:
    """Apply validated, non-persistent runtime paths to a copied config.

    This is the canonical bridge for notebook/hosted runtimes.  It never edits
    the source YAML, and records every effective input identity in the resolved
    config that the runner writes into the run directory.
    """

    resolved = json.loads(json.dumps(config))
    supplied = {
        "benchmark": benchmark_source,
        "corpus": corpus_source,
        "faiss_index": faiss_index_source,
        "faiss_payloads": faiss_payloads_source,
        "faiss_manifest": faiss_manifest_source,
        "graph": graph_source,
    }
    for label, source in supplied.items():
        if source is not None and not Path(source).is_file():
            raise AblationConfigError(f"Runtime {label} source is not a file: {Path(source).name}")

    if benchmark_source is not None:
        resolved["benchmark"]["path"] = str(Path(benchmark_source).resolve())
    if corpus_source is not None:
        resolved["corpus"]["path"] = str(Path(corpus_source).resolve())

    dense = resolved["retrieval"]["dense"]
    if faiss_index_source is not None:
        index_file = Path(faiss_index_source)
        if not index_file.is_absolute():
            index_file = (project_root / index_file).absolute()
        dense["index_path"] = str(index_file.parent)
        dense["index_file"] = str(index_file)
    if faiss_payloads_source is not None:
        payloads_file = Path(faiss_payloads_source)
        if not payloads_file.is_absolute():
            payloads_file = (project_root / payloads_file).absolute()
        dense["payloads_path"] = str(payloads_file)
    if faiss_manifest_source is not None:
        dense["manifest_path"] = str(Path(faiss_manifest_source).resolve())
    if graph_source is not None:
        resolved["retrieval"].setdefault("graph", {})["path"] = str(Path(graph_source).resolve())
    if runs_root is not None:
        resolved["output"]["root"] = str(Path(runs_root).resolve())
    if selected_device is not None:
        if selected_device not in {"cpu", "cuda"}:
            raise AblationConfigError("selected_device must be 'cpu' or 'cuda'.")
        resolved.setdefault("runtime", {})["selected_device"] = selected_device

    identities = resolved.setdefault("metadata", {}).setdefault("runtime_path_overrides", {})
    for label, source in supplied.items():
        if source is not None:
            identities[label] = str(Path(source).resolve())
    if runs_root is not None:
        identities["runs_root"] = str(Path(runs_root).resolve())
    return resolved


def build_case_executor(
    config: dict[str, Any], *, retriever: Any, generator: GeneratorFunction,
    sensitive_values: Sequence[str] = (),
) -> Callable[[dict[str, Any]], Any] | None:
    """Build the same optional per-case agent executor used by ablation runs."""

    return _build_case_executor(
        config, retriever=retriever, generator=generator, sensitive_values=sensitive_values
    )


def run_ablation_config(
    config_name: str,
    *,
    config_file: Path = DEFAULT_CONFIG_FILE,
    output_root: Path | None = None,
    run_id: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    retriever: Any | None = None,
    generator: GeneratorFunction | None = None,
    judge: JudgeFunction | None = None,
    command_args: Sequence[str] | None = None,
    project_root: Path = PROJECT_ROOT,
    resolved_config_override: Mapping[str, Any] | None = None,
) -> AblationRunOutcome:
    configs = load_ablation_configs(config_file)
    source_config = resolve_ablation_config(configs, config_name)
    config = (
        json.loads(json.dumps(resolved_config_override))
        if resolved_config_override is not None
        else source_config
    )
    validate_ablation_config(config, config_name=config_name)
    if dry_run:
        agent_mode = _agent_mode(config["agent"])
        deferred_reason = None
        if agent_mode is AgentMode.MULTI_TOOL:
            deferred_reason = str(config["agent"].get("reason") or "MultiTool implementation is deferred.")
        return AblationRunOutcome(
            config_name=config_name,
            status="deferred" if agent_mode is AgentMode.MULTI_TOOL else "completed",
            run_id=None,
            output_dir=None,
            artifacts={},
            counts={"total_input": 0, "successful": 0, "failed": 0, "skipped": 0, "evaluated": 0},
            error=deferred_reason,
        )
    _resolve_environment_model(config)
    validate_required_paths(config, project_root=project_root)

    config_hash = _config_hash(config)
    resolved_output_root = output_root or _resolved_path(config["output"]["root"], project_root)
    selected_run_id = run_id or create_run_id(config_name, config_hash=config_hash)
    output_dir = resolved_output_root / selected_run_id
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise AblationConfigError(f"Run directory already exists; refusing to overwrite: {output_dir}") from exc

    resolved_config_path = output_dir / "resolved_config.yaml"
    _write_yaml(resolved_config_path, config)
    manifest_path = output_dir / "manifest.json"
    started = datetime.now(timezone.utc)
    manifest = _initial_manifest(
        run_id=selected_run_id,
        config_name=config_name,
        config=config,
        config_file=config_file,
        config_hash=config_hash,
        started=started,
        command_args=command_args,
        output_dir=output_dir,
        case_limit=limit,
    )
    write_json(manifest_path, manifest)

    artifacts: dict[str, str] = {
        "manifest": str(manifest_path),
        "resolved_config": str(resolved_config_path),
    }
    counts = {"total_input": 0, "successful": 0, "failed": 0, "skipped": 0, "evaluated": 0}
    sensitive_values: list[str] = []
    try:
        judge_required = config.get("judge", {}).get("provider", "none") != "none"
        if retriever is None or generator is None or (judge_required and judge is None):
            built_retriever, built_generator, built_judge, sensitive_values = build_ablation_stack(
                config, project_root=project_root
            )
            retriever = retriever or built_retriever
            generator = generator or built_generator
            judge = judge or built_judge
        case_executor = _build_case_executor(
            config, retriever=retriever, generator=generator, sensitive_values=sensitive_values
        )
        benchmark_path = _resolved_path(config["benchmark"]["path"], project_root)
        result: E2ERunResult = run_e2e_evaluation(
            read_benchmark_records(benchmark_path, limit=limit),
            retriever=retriever,
            generator=generator,
            retrieval_top_k=int(config["retrieval"]["top_k"]),
            filter_profile=str(config["retrieval"].get("filter_profile") or "broad"),
            judge=judge,
            config=config,
            qa_path=str(benchmark_path),
            sensitive_values=sensitive_values,
            case_executor=case_executor,
        )
        artifacts.update(write_e2e_artifacts(output_dir, result, report_name="report.md"))
        counts = result.counts
        status = "needs-rerun" if counts["total_input"] and counts["successful"] == 0 else "completed"
        error = "All input cases failed or were skipped." if status == "needs-rerun" else None
    except UnsupportedComponentError as exc:
        status = "deferred"
        error = str(exc)
    except Exception as exc:
        status = "failed"
        error = str(exc)

    manifest.update(
        {
            "end_time": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "output_artifacts": artifacts,
            "completed_case_count": counts["successful"],
            "failed_case_count": counts["failed"],
            "skipped_case_count": counts["skipped"],
            "evaluated_case_count": counts["evaluated"],
            "error_summary": error,
        }
    )
    write_json(manifest_path, manifest)
    return AblationRunOutcome(
        config_name=config_name,
        status=status,
        run_id=selected_run_id,
        output_dir=output_dir,
        artifacts=artifacts,
        counts=counts,
        error=error,
    )


def create_run_id(config_name: str, *, config_hash: str, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S%fZ")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", config_name).strip("-").lower() or "config"
    return f"{timestamp}_{slug}_{config_hash[:8]}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one named ablation configuration.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-file", type=Path, default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        outcome = run_ablation_config(
            args.config,
            config_file=args.config_file,
            output_root=args.output_root,
            run_id=args.run_id,
            limit=args.limit,
            dry_run=args.dry_run,
            command_args=sys.argv[1:],
        )
    except AblationConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    print(f"Config: {outcome.config_name}")
    print(f"Status: {outcome.status}")
    if outcome.run_id:
        print(f"Run ID: {outcome.run_id}")
    if outcome.output_dir:
        print(f"Output: {outcome.output_dir}")
    if outcome.error:
        print(f"Error: {outcome.error}", file=sys.stderr)
    return 0 if outcome.status == "completed" or args.dry_run else 1


def _build_generator(config: dict[str, Any]) -> tuple[GeneratorFunction, list[str]]:
    provider = config["provider"]
    if provider == "reference":
        return (
            lambda qa, context, chunks: str(qa.get("reference_answer") or qa.get("answer") or ""),
            [],
        )
    api_key_env = str(config.get("api_key_env") or ("GEMINI_API_KEY" if provider == "gemini" else "LLM_API_KEY"))
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise AblationConfigError(f"Missing generation API key environment variable {api_key_env!r}.")
    model = str(config["model"])
    temperature = float(config.get("temperature", 0.0))
    top_p = float(config.get("top_p", 1.0))
    max_output_tokens = int(config.get("max_output_tokens", 1024))
    timeout_seconds = float(config.get("timeout_seconds", 60.0))
    max_retries = int(config.get("max_retries", 0))
    prompt_strategy = coerce_prompt_strategy(config.get("prompt_strategy"))
    if provider == "gemini":
        from scripts.evaluate_e2e import GeminiClient

        gemini_client = GeminiClient(api_key=api_key, rpm=int(config.get("rpm", 15)))

        def gemini_generate(qa: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
            del chunks
            content = gemini_client.generate(
                model=model,
                prompt=build_generation_prompt(
                    question=str(qa.get("question") or ""),
                    answer_type=str(qa.get("answer_type") or ""),
                    context=context,
                    strategy=prompt_strategy,
                ),
            )
            return parse_generation_response(
                RawGenerationResponse(content=content, reasoning_field=None)
            ).answer

        return gemini_generate, [api_key]

    base_url_env = str(config.get("base_url_env") or "LLM_BASE_URL")
    base_url = os.environ.get(base_url_env, "")
    if not base_url:
        raise AblationConfigError(f"Missing generator base URL environment variable {base_url_env!r}.")
    openai_client = GeneratorClient(base_url=base_url, api_key=api_key, model=model)

    def openai_generate(qa: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
        del context
        outcome = generate_answer(
            openai_client,
            str(qa.get("question") or ""),
            chunks,
            qa_id=str(qa.get("qa_id") or ""),
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            answer_type=str(qa.get("answer_type") or ""),
            prompt_strategy=prompt_strategy,
        )
        if outcome.error:
            raise RuntimeError(outcome.error)
        if outcome.skipped_empty_context or outcome.parsed is None:
            return "Không có đủ thông tin trong ngữ cảnh được cung cấp."
        return outcome.parsed.answer

    return openai_generate, [api_key]


def _build_judge(config: dict[str, Any]) -> tuple[JudgeFunction | None, list[str]]:
    if config["provider"] == "none":
        return None, []
    api_key_env = str(config.get("api_key_env") or "GEMINI_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise AblationConfigError(f"Missing judge API key environment variable {api_key_env!r}.")
    from scripts.evaluate_e2e import GeminiClient, judge_with_gemini

    judge_client = GeminiClient(api_key=api_key, rpm=int(config.get("rpm", 15)))
    model = str(config["model"])

    def judge(
        qa: dict[str, Any],
        reference_answer: str,
        predicted: str,
        context: str,
    ) -> dict[str, Any]:
        return judge_with_gemini(judge_client, model, qa, reference_answer, predicted, context)

    return judge, [api_key]


def _initial_manifest(
    *,
    run_id: str,
    config_name: str,
    config: dict[str, Any],
    config_file: Path,
    config_hash: str,
    started: datetime,
    command_args: Sequence[str] | None,
    output_dir: Path,
    case_limit: int | None = None,
) -> dict[str, Any]:
    git_commit, git_dirty = _git_state()
    dense = config["retrieval"]["dense"]
    graph = config["retrieval"].get("graph", {})
    generation = config["generation"]
    agent = config["agent"]
    agent_mode = _agent_mode(agent)
    strategy = coerce_prompt_strategy(generation.get("prompt_strategy"))
    return {
        "run_id": run_id,
        "config_name": config_name,
        "resolved_config": config,
        "config_file_path": str(config_file.resolve()),
        "config_hash": config_hash,
        "start_time": started.isoformat(),
        "end_time": None,
        "status": "running",
        "case_limit": case_limit,
        "benchmark_path": config["benchmark"]["path"],
        "benchmark_version": config["benchmark"]["version"],
        "corpus_path": config["corpus"]["path"],
        "corpus_version": config["corpus"]["version"],
        "index_path": dense.get("index_path"),
        "index_version": dense.get("index_version"),
        "graph_path": graph.get("path"),
        "graph_version": graph.get("version"),
        "selected_retrieval_stack": config["retrieval"],
        "selected_generation_stack": config["generation"],
        "generation_provider": generation["provider"],
        "generation_model": generation["model"],
        "prompt_strategy": strategy.value,
        "prompt_template_version": generation.get(
            "prompt_template_version", PROMPT_TEMPLATE_VERSION
        ),
        "prompt_template_hash": prompt_template_hash(strategy),
        "citation_contract_version": CITATION_CONTRACT_VERSION,
        "citation_contract_hash": citation_contract_hash(),
        "generation_decoding": {
            "temperature": float(generation.get("temperature", 0.0)),
            "top_p": float(generation.get("top_p", 1.0)),
            "max_output_tokens": int(generation.get("max_output_tokens", 1024)),
            "timeout_seconds": float(generation.get("timeout_seconds", 60.0)),
            "max_retries": int(generation.get("max_retries", 0)),
        },
        "selected_agent_stack": config["agent"],
        "agent_mode": agent_mode.value,
        "agent_enabled": bool(agent.get("enabled")),
        "agent_version": AGENT_VERSION,
        "planner_policy": PLANNER_POLICY if agent_mode is AgentMode.SIMPLE_PLANNER else None,
        "planner_policy_version": PLANNER_POLICY_VERSION if agent_mode is AgentMode.SIMPLE_PLANNER else None,
        "planner_prompt_hash": None,
        "max_steps": agent.get("max_steps"),
        "max_tool_calls": agent.get("max_tool_calls"),
        "allowed_tools": agent.get("allowed_tools", []),
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "tool_contract_version": TOOL_CONTRACT_VERSION,
        "seed": config.get("seed", 42),
        "hostname": socket.gethostname(),
        "execution_environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "packages": _package_versions(["PyYAML", "google-genai", "openai", "faiss-cpu", "sentence-transformers"]),
            "selected_device": config.get("runtime", {}).get("selected_device", "cpu"),
        },
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "command_line_arguments": list(command_args or []),
        "output_directory": str(output_dir),
        "output_artifacts": {},
        "completed_case_count": 0,
        "failed_case_count": 0,
        "skipped_case_count": 0,
        "evaluated_case_count": 0,
        "error_summary": None,
    }


def _agent_mode(agent: Mapping[str, Any]) -> AgentMode:
    value = agent.get("mode", "none" if not agent.get("enabled") else agent.get("type"))
    return AgentMode.NONE if value == "plain_rag" else coerce_agent_mode(value)


def _build_case_executor(
    config: dict[str, Any], *, retriever: Any, generator: GeneratorFunction,
    sensitive_values: Sequence[str],
) -> Callable[[dict[str, Any]], Any] | None:
    agent = config["agent"]
    mode = _agent_mode(agent)
    if mode is AgentMode.NONE:
        return None
    if mode is AgentMode.MULTI_TOOL:
        raise UnsupportedComponentError(
            "Agent-MultiTool-Orchestrated is deferred: only the typed read-only retrieval tool is stable; "
            "a second approved typed tool and bounded orchestration acceptance contract are missing."
        )
    tool = RetrievalTool(retriever, sensitive_values=sensitive_values)
    planner = SimplePlanner(
        retrieval_tool=tool, generator=generator, top_k=int(config["retrieval"]["top_k"]),
        filter_profile=str(config["retrieval"].get("filter_profile") or "broad"),
        max_steps=int(agent["max_steps"]), max_tool_calls=int(agent["max_tool_calls"]),
        max_retries=int(agent.get("max_retries", 0)),
        deadline_seconds=float(agent["deadline_seconds"]),
    )
    return planner.execute


def _require_mapping(parent: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise AblationConfigError(f"{context}.{key} must be a mapping.")
    return value


def _require_non_empty_string(parent: dict[str, Any], key: str, context: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AblationConfigError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_bool(parent: dict[str, Any], key: str, context: str) -> None:
    if key not in parent or not isinstance(parent[key], bool):
        raise AblationConfigError(f"{context}.{key} must be a boolean.")


def _validate_number(
    parent: dict[str, Any],
    key: str,
    config_name: str,
    *,
    minimum: float,
    maximum: float | None = None,
    exclusive_minimum: bool = False,
) -> None:
    if key not in parent:
        return
    value = parent[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AblationConfigError(f"{config_name}.generation.{key} must be numeric.")
    if (exclusive_minimum and value <= minimum) or (not exclusive_minimum and value < minimum):
        operator = "greater than" if exclusive_minimum else "at least"
        raise AblationConfigError(
            f"{config_name}.generation.{key} must be {operator} {minimum}."
        )
    if maximum is not None and value > maximum:
        raise AblationConfigError(
            f"{config_name}.generation.{key} must be at most {maximum}."
        )


def _validate_integer(
    parent: dict[str, Any],
    key: str,
    config_name: str,
    *,
    minimum: int,
) -> None:
    if key not in parent:
        return
    value = parent[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise AblationConfigError(
            f"{config_name}.generation.{key} must be an integer of at least {minimum}."
        )


def _resolve_environment_model(config: dict[str, Any]) -> None:
    generation = config["generation"]
    configured = str(generation["model"])
    if not configured.startswith("env:"):
        return
    environment_name = configured.removeprefix("env:").strip()
    if not environment_name:
        raise AblationConfigError("Generation model environment selector is empty.")
    resolved = os.environ.get(environment_name, "").strip()
    if not resolved:
        raise AblationConfigError(
            f"Missing generation model environment variable {environment_name!r}."
        )
    generation["model"] = resolved
    generation["model_env"] = environment_name


def _resolved_path(value: str | Path, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _config_hash(config: dict[str, Any]) -> str:
    encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    import yaml  # type: ignore[import-untyped]

    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _env_value(name: Any) -> str | None:
    return os.environ.get(str(name)) if isinstance(name, str) and name else None


def _git_state() -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def _package_versions(names: Sequence[str]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


if __name__ == "__main__":
    raise SystemExit(main())
