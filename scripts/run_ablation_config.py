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
from evaluation.io_utils import write_json  # noqa: E402
from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever  # noqa: E402
from generation.reasoning_client import GeneratorClient, generate_answer  # noqa: E402


DEFAULT_CONFIG_FILE = PROJECT_ROOT / "configs" / "ablation_configs.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "evaluation_runs" / "ablation"
SUPPORTED_DENSE_BACKENDS = {"faiss", "qdrant", "hashing"}
SUPPORTED_GENERATORS = {"reference", "gemini", "openai_compatible"}
SUPPORTED_JUDGES = {"none", "gemini"}
RUN_STATUSES = {"completed", "failed", "skipped", "deferred", "needs-rerun"}


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
        if backend == "faiss":
            _require_non_empty_string(dense, "index_path", f"{config_name}.retrieval.dense")
        if backend == "qdrant":
            _require_non_empty_string(dense, "collection", f"{config_name}.retrieval.dense")

    enabled_retrievers = bool(dense["enabled"])
    for component in ("sparse", "graph", "fusion", "reranker"):
        section = retrieval.get(component, {"enabled": False})
        if not isinstance(section, dict):
            raise AblationConfigError(f"{config_name}.retrieval.{component} must be a mapping.")
        _require_bool(section, "enabled", f"{config_name}.retrieval.{component}")
        if component in {"sparse", "graph"}:
            enabled_retrievers = enabled_retrievers or bool(section["enabled"])
    if not enabled_retrievers:
        raise AblationConfigError(f"{config_name} must enable at least one retriever.")

    provider = _require_non_empty_string(generation, "provider", f"{config_name}.generation")
    if provider not in SUPPORTED_GENERATORS:
        raise AblationConfigError(
            f"Unsupported generation provider {provider!r}; expected one of {sorted(SUPPORTED_GENERATORS)}."
        )
    _require_non_empty_string(generation, "model", f"{config_name}.generation")
    if "temperature" in generation and not isinstance(generation["temperature"], (int, float)):
        raise AblationConfigError(f"{config_name}.generation.temperature must be numeric.")

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
    seed = config.get("seed", 42)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise AblationConfigError(f"{config_name}.seed must be an integer.")
    if "metadata" in config and not isinstance(config["metadata"], dict):
        raise AblationConfigError(f"{config_name}.metadata must be a mapping.")


def validate_required_paths(config: dict[str, Any], *, project_root: Path = PROJECT_ROOT) -> None:
    required = [
        ("benchmark.path", _resolved_path(config["benchmark"]["path"], project_root)),
        ("corpus.path", _resolved_path(config["corpus"]["path"], project_root)),
    ]
    dense = config["retrieval"]["dense"]
    if dense["enabled"] and dense["backend"] == "faiss":
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
    for component in ("sparse", "graph", "fusion", "reranker"):
        section = retrieval.get(component, {})
        if section.get("enabled"):
            name = section.get("backend") or section.get("strategy") or section.get("model") or component
            raise UnsupportedComponentError(
                f"Configured {component} component {name!r} is not integrated with scripts/run_ablation_config.py."
            )
    if config["agent"]["enabled"]:
        agent_type = config["agent"].get("type") or "unspecified"
        raise UnsupportedComponentError(
            f"Configured agent {agent_type!r} is not integrated with scripts/run_ablation_config.py."
        )

    dense = retrieval["dense"]
    if not dense["enabled"]:
        raise UnsupportedComponentError("The current runner requires retrieval.dense.enabled=true.")
    backend = dense["backend"]
    runtime = RetrieverRuntimeConfig(
        store="faiss" if backend in {"faiss", "hashing"} else "qdrant",
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
    )
    retriever = build_vector_retriever(runtime)
    generator, generator_secrets = _build_generator(config["generation"])
    judge, judge_secrets = _build_judge(config.get("judge", {"provider": "none"}))
    qdrant_key = runtime.qdrant_api_key or ""
    return retriever, generator, judge, [*generator_secrets, *judge_secrets, qdrant_key]


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
) -> AblationRunOutcome:
    configs = load_ablation_configs(config_file)
    config = resolve_ablation_config(configs, config_name)
    validate_ablation_config(config, config_name=config_name)
    if dry_run:
        return AblationRunOutcome(
            config_name=config_name,
            status="completed",
            run_id=None,
            output_dir=None,
            artifacts={},
            counts={"total_input": 0, "successful": 0, "failed": 0, "skipped": 0, "evaluated": 0},
        )
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
    return 0 if outcome.status == "completed" else 1


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
    if provider == "gemini":
        from scripts.evaluate_e2e import ANSWER_PROMPT, GeminiClient

        gemini_client = GeminiClient(api_key=api_key, rpm=int(config.get("rpm", 15)))

        def gemini_generate(qa: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
            del chunks
            return gemini_client.generate(
                model=model,
                prompt=ANSWER_PROMPT.format(
                    question=qa.get("question") or "",
                    answer_type=qa.get("answer_type") or "",
                    context=context,
                ),
            )

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
) -> dict[str, Any]:
    git_commit, git_dirty = _git_state()
    dense = config["retrieval"]["dense"]
    graph = config["retrieval"].get("graph", {})
    return {
        "run_id": run_id,
        "config_name": config_name,
        "resolved_config": config,
        "config_file_path": str(config_file.resolve()),
        "config_hash": config_hash,
        "start_time": started.isoformat(),
        "end_time": None,
        "status": "running",
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
        "selected_agent_stack": config["agent"],
        "seed": config.get("seed", 42),
        "hostname": socket.gethostname(),
        "execution_environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "packages": _package_versions(["PyYAML", "google-genai", "openai", "faiss-cpu", "sentence-transformers"]),
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
