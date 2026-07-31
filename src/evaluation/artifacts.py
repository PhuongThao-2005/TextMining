"""Safe loaders and display normalization for existing E2E run artifacts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from .e2e_runner import LATENCY_STAGES, sanitize_error_text


MANDATORY_COMPLETED_ARTIFACTS = (
    "resolved_config.yaml",
    "e2e_predictions.jsonl",
    "e2e_metrics.json",
    "latency.json",
    "errors.jsonl",
    "report.md",
)
VALID_RUN_MODES = frozenset({"smoke", "full", "inspect"})
CANONICAL_ARTIFACTS = {
    "manifest": "manifest.json", "resolved_config": "resolved_config.yaml",
    "predictions": "e2e_predictions.jsonl", "metrics": "e2e_metrics.json",
    "latency": "latency.json", "errors": "errors.jsonl", "report": "report.md",
}


class ArtifactLoadError(RuntimeError):
    """A run directory cannot be inspected safely."""


ArtifactError = ArtifactLoadError


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    manifest: dict[str, Any]
    resolved_config: dict[str, Any] | None
    predictions: tuple[dict[str, Any], ...]
    metrics: dict[str, Any] | None
    retrieval_metrics: dict[str, Any] | None
    latency: dict[str, Any] | None
    errors: tuple[dict[str, Any], ...]
    report: str | None
    diagnostics: tuple[str, ...]

    @property
    def status(self) -> str:
        return str(self.manifest.get("status") or "validation-error")


def validate_run_parameters(
    run_mode: str, *, smoke_limit: int, existing_run_dir: Path | None,
) -> None:
    if run_mode not in VALID_RUN_MODES:
        raise ValueError(f"RUN_MODE must be one of {sorted(VALID_RUN_MODES)}.")
    if not isinstance(smoke_limit, int) or isinstance(smoke_limit, bool) or not 1 <= smoke_limit <= 100:
        raise ValueError("SMOKE_LIMIT must be an integer from 1 through 100.")
    if run_mode == "inspect" and existing_run_dir is None:
        raise ValueError("EXISTING_RUN_DIR is required in inspect mode.")


def load_run_artifacts(run_dir: Path, *, require_completed: bool = False) -> RunArtifacts:
    """Load the canonical runner artifacts without requiring a completed run."""

    directory = Path(run_dir).resolve()
    manifest_path = directory / "manifest.json"
    if not directory.is_dir():
        raise ArtifactLoadError(f"Run directory does not exist: {directory.name}")
    if not manifest_path.is_file():
        raise ArtifactLoadError("Run directory is missing manifest.json.")
    manifest = _load_json_object(manifest_path, required=True)
    assert manifest is not None
    manifest = cast(dict[str, Any], _redact_mapping(manifest))
    diagnostics: list[str] = []

    resolved = _load_yaml_object(directory / "resolved_config.yaml", diagnostics)
    predictions = _load_jsonl(directory / "e2e_predictions.jsonl", "predictions", diagnostics)
    metrics = _load_optional_json(directory / "e2e_metrics.json", "E2E metrics", diagnostics)
    retrieval = _load_optional_json(directory / "retrieval_metrics.json", "retrieval metrics", diagnostics)
    latency = _load_optional_json(directory / "latency.json", "latency", diagnostics)
    errors = tuple(_sanitize_error_row(row) for row in _load_jsonl(directory / "errors.jsonl", "errors", diagnostics))
    report = _load_optional_text(directory / "report.md", "report", diagnostics)

    if str(manifest.get("status")) == "completed":
        missing: list[str] = []
        for filename in MANDATORY_COMPLETED_ARTIFACTS:
            if not (directory / filename).is_file():
                diagnostics.append(f"Completed run is missing mandatory artifact: {filename}.")
                missing.append(filename)
        if require_completed and missing:
            raise ArtifactLoadError(f"Completed run is missing canonical artifacts: {', '.join(missing)}")
    return RunArtifacts(
        directory, manifest, resolved, tuple(_sanitize_prediction(row) for row in predictions),
        metrics, retrieval, latency, errors, report, tuple(diagnostics),
    )


def run_summary_rows(artifacts: RunArtifacts, *, repo_root: Path | None = None) -> list[dict[str, Any]]:
    manifest = artifacts.manifest
    fields = {
        "run_id": manifest.get("run_id"),
        "config_name": manifest.get("config_name"),
        "status": manifest.get("status"),
        "run_directory": repository_relative_path(artifacts.run_dir, repo_root) if repo_root else artifacts.run_dir.name,
        "started_at": manifest.get("start_time"),
        "completed_at": manifest.get("end_time"),
        "case_limit": manifest.get("case_limit"),
        "attempted_cases": _count(manifest, artifacts.metrics, "total_input"),
        "successful_cases": manifest.get("completed_case_count"),
        "failed_cases": manifest.get("failed_case_count"),
        "skipped_cases": manifest.get("skipped_case_count"),
        "deferred_cases": manifest.get("deferred_case_count"),
        "benchmark_identity": _identity(manifest, "benchmark"),
        "corpus_identity": _identity(manifest, "corpus"),
        "git_commit": manifest.get("git_commit"),
        "prompt_strategy": manifest.get("prompt_strategy"),
        "model": manifest.get("generation_model"),
        "agent_mode": manifest.get("agent_mode") or _nested(manifest, "resolved_config", "agent", "mode"),
    }
    return [{"field": key, "value": value} for key, value in fields.items()]


def prediction_table_rows(
    predictions: Sequence[Mapping[str, Any]], *, agent_mode: str | None = None, max_chars: int = 160,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        contexts = prediction.get("retrieved_context")
        latency = prediction.get("latency_ms")
        error = prediction.get("error")
        status = prediction.get("status")
        rows.append({
            "case_id": prediction.get("qa_id") or prediction.get("case_id"),
            "question": _truncate(prediction.get("question"), max_chars),
            "status": status,
            "reference_answer": _truncate(prediction.get("reference_answer"), max_chars),
            "predicted_answer": _truncate(prediction.get("predicted_answer"), max_chars),
            "abstained": status == "skipped" or prediction.get("agent_status") == "abstained",
            "exact_match": prediction.get("exact_match"),
            "token_f1": prediction.get("token_f1"),
            "rouge_l": prediction.get("rouge_l"),
            "unanswerable_correct": prediction.get("unanswerable_accuracy"),
            "context_recall_at_k": prediction.get("context_recall@k"),
            "retrieved_count": len(contexts) if isinstance(contexts, list) else 0,
            "failure_stage": prediction.get("failed_stage"),
            "error_type": error.get("type") if isinstance(error, Mapping) else None,
            "total_latency_ms": latency.get("total") if isinstance(latency, Mapping) else None,
            "agent_mode": agent_mode,
            "tool_calls": prediction.get("tool_call_count"),
            "planner_abstained": prediction.get("agent_status") == "abstained",
            "agent_failure": prediction.get("agent_status") == "failed",
        })
    return rows


def grouped_metric_rows(metrics: Mapping[str, Any] | None, group_key: str) -> list[dict[str, Any]]:
    groups = metrics.get(group_key) if isinstance(metrics, Mapping) else None
    if not isinstance(groups, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for name in sorted(groups, key=str):
        values = groups[name]
        if not isinstance(values, Mapping):
            continue
        rows.append({
            "group": name,
            "case_count": values.get("count"),
            "successful_count": values.get("count"),
            "failed_or_skipped_count": None,
            "exact_match": values.get("exact_match"),
            "token_f1": values.get("token_f1"),
            "rouge_l": values.get("rouge_l"),
            "unanswerable_accuracy": values.get("unanswerable_accuracy"),
            "context_recall_at_k": values.get("context_recall@k"),
        })
    return rows


def latency_summary_rows(latency: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    stages = latency.get("stages") if isinstance(latency, Mapping) else None
    stages = stages if isinstance(stages, Mapping) else {}
    rows: list[dict[str, Any]] = []
    for stage in LATENCY_STAGES:
        values = stages.get(stage)
        rows.append({
            "stage": stage,
            "count": values.get("count") if isinstance(values, Mapping) else None,
            "mean_ms": values.get("mean") if isinstance(values, Mapping) else None,
            "median_ms": values.get("median") if isinstance(values, Mapping) else None,
            "min_ms": values.get("min") if isinstance(values, Mapping) else None,
            "max_ms": values.get("max") if isinstance(values, Mapping) else None,
            "p95_ms": values.get("p95") if isinstance(values, Mapping) else None,
        })
    return rows


def normalize_context_rows(items: Sequence[Any], *, preview_chars: int = 300) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fallback_rank, item in enumerate(items, 1):
        value = item if isinstance(item, Mapping) else vars(item)
        text = str(value.get("text") or value.get("chunk_text") or "")
        rank = value.get("rank") if isinstance(value.get("rank"), int) else fallback_rank
        rows.append({
            "rank": rank,
            "score": value.get("score"),
            "vector_score": value.get("vector_score"),
            "reranker_score": value.get("rerank_score"),
            "document_id": value.get("document_id") or value.get("id_str"),
            "chunk_id": value.get("chunk_id"),
            "title": value.get("title"),
            "article_or_section": value.get("article_number") or value.get("provision_id"),
            "source_path": value.get("path"),
            "context_reference": value.get("citation") or value.get("citation_anchor") or value.get("citation_label"),
            "preview": _truncate(text, preview_chars),
            "text": text,
        })
    return sorted(rows, key=lambda row: (row["rank"], str(row.get("chunk_id") or "")))


def normalize_trace_rows(trace: Sequence[Any], *, maximum_events: int = 10) -> list[dict[str, Any]]:
    allowed = ("step", "event", "action", "reason_code", "tool", "status", "result_count", "latency_ms", "error_type")
    rows = []
    for index, item in enumerate(trace[:maximum_events]):
        value = item if isinstance(item, Mapping) else vars(item)
        row = {key: value.get(key) for key in allowed if value.get(key) is not None}
        rows.append((row.get("step") if isinstance(row.get("step"), int) else 10_000 + index, index, row))
    return [row for _, _, row in sorted(rows)]


def repository_relative_path(path: Path, repo_root: Path | None) -> str:
    resolved = Path(path).resolve()
    if repo_root is None:
        return resolved.name
    try:
        return resolved.relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return resolved.name


def artifact_relative_paths(artifacts: RunArtifacts, repo_root: Path) -> list[str]:
    names = ["manifest.json", *MANDATORY_COMPLETED_ARTIFACTS, "retrieval_metrics.json"]
    return [
        repository_relative_path(artifacts.run_dir / name, repo_root)
        for name in names
        if (artifacts.run_dir / name).is_file()
    ]


def _load_json_object(path: Path, *, required: bool) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        if required:
            raise ArtifactLoadError(f"Unable to load {path.name}: {sanitize_error_text(exc)}") from None
        return None
    if not isinstance(value, dict):
        if required:
            raise ArtifactLoadError(f"{path.name} must contain a JSON object.")
        return None
    return value


def _load_optional_json(path: Path, label: str, diagnostics: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        diagnostics.append(f"Optional {label} artifact is unavailable: {path.name}.")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("root must be an object")
        return value
    except Exception as exc:
        diagnostics.append(f"Malformed {label} artifact {path.name}: {sanitize_error_text(exc)}")
        return None


def _load_jsonl(path: Path, label: str, diagnostics: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        diagnostics.append(f"Optional {label} artifact is unavailable: {path.name}.")
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"line {line_number} is not an object")
            rows.append(value)
    except Exception as exc:
        diagnostics.append(f"Malformed {label} artifact {path.name}: {sanitize_error_text(exc)}")
        return []
    return rows


def _load_yaml_object(path: Path, diagnostics: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        diagnostics.append(f"Optional resolved config artifact is unavailable: {path.name}.")
        return None
    try:
        import yaml  # type: ignore[import-untyped]
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("root must be an object")
        return _redact_mapping(value)
    except Exception as exc:
        diagnostics.append(f"Malformed resolved config artifact {path.name}: {sanitize_error_text(exc)}")
        return None


def _load_optional_text(path: Path, label: str, diagnostics: list[str]) -> str | None:
    if not path.is_file():
        diagnostics.append(f"Optional {label} artifact is unavailable: {path.name}.")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        diagnostics.append(f"Unable to read {label} artifact {path.name}: {sanitize_error_text(exc)}")
        return None


def _sanitize_error_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": row.get("case_id") or row.get("qa_id"),
        "stage": row.get("stage"),
        "error_type": row.get("exception_type") or row.get("error_type"),
        "safe_message": sanitize_error_text(row.get("message") or ""),
        "retry_count": row.get("retry_count"),
        "timestamp": row.get("timestamp"),
    }


def _sanitize_prediction(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    error = value.get("error")
    if isinstance(error, Mapping):
        value["error"] = {
            "type": error.get("type"),
            "message": sanitize_error_text(error.get("message") or ""),
        }
    trace = value.get("agent_trace")
    if isinstance(trace, list):
        value["agent_trace"] = normalize_trace_rows(trace)
    return value


def _redact_mapping(value: Any, key_name: str = "") -> Any:
    lowered = key_name.lower()
    if lowered and not lowered.endswith("_env") and any(marker in lowered for marker in ("api_key", "authorization", "secret", "token", "password")):
        return "***"
    if isinstance(value, Mapping):
        return {str(key): _redact_mapping(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_mapping(item) for item in value]
    return value


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _identity(manifest: Mapping[str, Any], name: str) -> str | None:
    path = manifest.get(f"{name}_path")
    version = manifest.get(f"{name}_version")
    if path is None and version is None:
        return None
    return f"{Path(str(path)).name if path else 'N/A'} @ {version or 'N/A'}"


def _count(manifest: Mapping[str, Any], metrics: Mapping[str, Any] | None, key: str) -> Any:
    counts = metrics.get("counts") if isinstance(metrics, Mapping) else None
    if isinstance(counts, Mapping) and key in counts:
        return counts[key]
    return manifest.get(f"{key}_case_count")


def _truncate(value: object, maximum: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= maximum else text[: max(0, maximum - 1)].rstrip() + "…"


__all__ = [
    "ArtifactError", "ArtifactLoadError", "CANONICAL_ARTIFACTS", "MANDATORY_COMPLETED_ARTIFACTS", "RunArtifacts", "VALID_RUN_MODES",
    "artifact_relative_paths", "grouped_metric_rows", "latency_summary_rows", "load_run_artifacts",
    "normalize_context_rows", "normalize_trace_rows", "prediction_table_rows", "repository_relative_path",
    "run_summary_rows", "validate_run_parameters",
]
