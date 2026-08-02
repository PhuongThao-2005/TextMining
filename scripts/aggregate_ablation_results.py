#!/usr/bin/env python3
"""Validate and aggregate ablation run artifacts into deterministic reports."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.e2e_runner import LATENCY_STAGES, _sanitize_text  # noqa: E402
from scripts.run_ablation_config import RUN_STATUSES  # noqa: E402


DEFAULT_RUNS_DIR = PROJECT_ROOT / "evaluation_runs" / "ablation"
SUMMARY_NAME = "ablation_summary.csv"
REPORT_NAME = "ablation_report.md"
KNOWN_STATUSES = RUN_STATUSES | {"running", "validation-error"}
PARTIAL_STATUSES = {"needs-rerun", "running"}
IGNORED_DIRECTORY_NAMES = {
    "__pycache__",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "cache",
    "tmp",
    "temp",
}
REQUIRED_MANIFEST_FIELDS = (
    "run_id",
    "config_name",
    "resolved_config",
    "config_hash",
    "start_time",
    "end_time",
    "status",
    "benchmark_path",
    "benchmark_version",
    "corpus_path",
    "corpus_version",
    "output_directory",
    "output_artifacts",
    "completed_case_count",
    "failed_case_count",
    "skipped_case_count",
    "evaluated_case_count",
)

CSV_COLUMNS = [
    "run_id",
    "config_name",
    "config_hash",
    "generation_provider",
    "generation_model",
    "prompt_strategy",
    "prompt_template_version",
    "prompt_template_hash",
    "temperature",
    "top_p",
    "max_output_tokens",
    "timeout_seconds",
    "max_retries",
    "agent_mode",
    "agent_version",
    "planner_policy",
    "max_steps",
    "max_tool_calls",
    "allowed_tools",
    "status",
    "eligible_for_comparison",
    "exclusion_reason",
    "benchmark_name",
    "benchmark_version",
    "corpus_name",
    "corpus_version",
    "evaluation_schema_version",
    "index_version",
    "graph_version",
    "created_at",
    "completed_at",
    "git_commit",
    "exact_match",
    "token_f1",
    "rouge_l",
    "unanswerable_accuracy",
    "context_recall_at_k",
    "recall_at_1",
    "recall_at_5",
    "recall_at_10",
    "mrr",
    "ndcg",
    "average_total_latency_ms",
    "median_total_latency_ms",
    "p95_total_latency_ms",
    "dense_retrieval_latency_ms",
    "sparse_retrieval_latency_ms",
    "graph_traversal_latency_ms",
    "fusion_latency_ms",
    "reranker_latency_ms",
    "generation_latency_ms",
    "judge_latency_ms",
    "serialization_latency_ms",
    "average_planner_latency_ms",
    "average_tool_retrieval_latency_ms",
    "average_agent_total_latency_ms",
    "tool_call_success_rate",
    "retrieval_invocation_rate",
    "average_tool_calls_per_case",
    "planner_abstention_rate",
    "step_limit_failure_rate",
    "empty_context_rate",
    "agent_failure_rate",
    "citation_validity_rate",
    "average_structural_citation_coverage",
    "average_unique_cited_sources",
    "cases_with_invalid_citations",
    "cases_with_no_valid_citation",
    "successful_cases",
    "failed_cases",
    "skipped_cases",
    "deferred_cases",
    "notes",
    "run_directory",
]


class AggregationError(RuntimeError):
    """A fatal invocation or output error."""


@dataclass
class RunRecord:
    """One discovered run and its validation/aggregation state."""

    directory: Path
    manifest_path: Path
    manifest: dict[str, Any] | None = None
    run_id: str = ""
    config_name: str = ""
    status: str = "validation-error"
    config_hash: str = ""
    validation_errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metrics: dict[str, float | int | None] = field(default_factory=dict)
    compatible_key: tuple[str, ...] | None = None
    eligible_for_comparison: bool = False
    exclusion_reason: str = ""

    @property
    def valid(self) -> bool:
        return not self.validation_errors and self.status != "validation-error"


@dataclass(frozen=True)
class AggregationResult:
    """Public result returned after aggregate outputs have been written."""

    runs: tuple[RunRecord, ...]
    output_csv: Path
    output_report: Path
    selected_compatibility_group: tuple[str, ...] | None

    @property
    def discovered_count(self) -> int:
        return len(self.runs)

    @property
    def comparable_count(self) -> int:
        return sum(run.eligible_for_comparison for run in self.runs)

    @property
    def invalid_count(self) -> int:
        return sum(not run.valid for run in self.runs)

    @property
    def excluded_count(self) -> int:
        return self.discovered_count - self.comparable_count


def discover_run_directories(runs_dir: Path) -> list[Path]:
    """Return sorted directories containing a manifest, at any depth."""

    if not runs_dir.exists():
        raise AggregationError(
            f"Runs directory does not exist: {runs_dir}. Create it or pass an existing directory with --runs-dir."
        )
    if not runs_dir.is_dir():
        raise AggregationError(f"Runs path is not a directory: {runs_dir}")
    directories = {
        path.parent
        for path in runs_dir.rglob("manifest.json")
        if path.is_file()
        and not any(
            part.casefold() in IGNORED_DIRECTORY_NAMES
            or part.casefold().endswith((".tmp", ".temp"))
            for part in path.relative_to(runs_dir).parts[:-1]
        )
    }
    return sorted(directories, key=lambda path: _display_path(path, runs_dir).casefold())


def load_run(run_dir: Path) -> RunRecord:
    """Load and validate one manifest and its applicable artifacts."""

    manifest_path = run_dir / "manifest.json"
    record = RunRecord(directory=run_dir, manifest_path=manifest_path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        record.validation_errors.append(f"Malformed manifest.json: {_safe_error(exc)}")
        record.run_id = run_dir.name
        record.notes.append("Identity recovered from the run directory name.")
        return record
    if not isinstance(payload, dict):
        record.validation_errors.append("manifest.json root must be a JSON object.")
        record.run_id = run_dir.name
        return record

    record.manifest = payload
    record.run_id = _string(payload.get("run_id")) or run_dir.name
    record.config_name = _string(payload.get("config_name"))
    record.status = _string(payload.get("status")) or "validation-error"
    record.config_hash = _string(payload.get("config_hash"))
    _validate_manifest(record)
    _validate_llm_comparison_metadata(record)
    _validate_agent_comparison_metadata(record)

    if _string(payload.get("run_id")) and run_dir.name != record.run_id:
        record.validation_errors.append(
            f"Directory name {run_dir.name!r} does not match manifest run_id {record.run_id!r}."
        )

    if record.status == "completed":
        _load_completed_artifacts(record)
    else:
        error_summary = _string(payload.get("error_summary"))
        if error_summary:
            record.notes.append(f"Runner error: {_sanitize_text(error_summary, ())}")
        record.notes.append(f"Metrics not required for {record.status!r} status.")
    _validate_supporting_artifacts(record)
    record.compatible_key = _compatibility_key(record)
    return record


def _validate_manifest(record: RunRecord) -> None:
    assert record.manifest is not None
    manifest = record.manifest
    for field_name in REQUIRED_MANIFEST_FIELDS:
        if field_name not in manifest:
            record.validation_errors.append(f"Missing required manifest field: {field_name}.")
    for field_name in (
        "run_id",
        "config_name",
        "config_hash",
        "start_time",
        "benchmark_path",
        "benchmark_version",
        "corpus_path",
        "corpus_version",
        "output_directory",
    ):
        if field_name in manifest and not _string(manifest.get(field_name)):
            record.validation_errors.append(f"Manifest field {field_name!r} must be a non-empty string.")
    if "resolved_config" in manifest and not isinstance(manifest.get("resolved_config"), dict):
        record.validation_errors.append("Manifest field 'resolved_config' must be an object.")
    if "output_artifacts" in manifest and not isinstance(manifest.get("output_artifacts"), dict):
        record.validation_errors.append("Manifest field 'output_artifacts' must be an object.")
    if record.status not in KNOWN_STATUSES:
        record.validation_errors.append(
            f"Invalid status {record.status!r}; expected one of {sorted(KNOWN_STATUSES)}."
        )
    for field_name in (
        "completed_case_count",
        "failed_case_count",
        "skipped_case_count",
        "evaluated_case_count",
    ):
        value = manifest.get(field_name)
        if field_name in manifest and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            record.validation_errors.append(f"Manifest field {field_name!r} must be a non-negative integer.")
    if record.status == "completed" and not _string(manifest.get("end_time")):
        record.validation_errors.append("Completed run is missing a non-empty end_time.")


def _validate_llm_comparison_metadata(record: RunRecord) -> None:
    """Require the comparison contract for new named LLM runs without breaking old runs."""

    if (
        record.status != "completed"
        or record.config_name
        not in {"LLM-BaseReasoning", "LLM-CoTReasoning", "LLM-LargerModel"}
    ):
        return
    manifest = record.manifest or {}
    required = {
        "generation_provider": _generation_value(manifest, "provider"),
        "generation_model": _generation_value(manifest, "model"),
        "prompt_strategy": _generation_value(manifest, "prompt_strategy"),
        "prompt_template_version": _generation_value(manifest, "prompt_template_version"),
        "prompt_template_hash": manifest.get("prompt_template_hash"),
        "temperature": _decoding_value(manifest, "temperature"),
        "top_p": _decoding_value(manifest, "top_p"),
        "max_output_tokens": _decoding_value(manifest, "max_output_tokens"),
        "timeout_seconds": _decoding_value(manifest, "timeout_seconds"),
        "max_retries": _decoding_value(manifest, "max_retries"),
    }
    missing = [name for name, value in required.items() if value is None or value == ""]
    if missing:
        record.validation_errors.append(
            "Completed LLM run is missing critical comparison metadata: "
            + ", ".join(missing)
            + "."
        )


def _validate_agent_comparison_metadata(record: RunRecord) -> None:
    """Require critical metadata only for completed named executable agent runs."""
    if record.status != "completed" or record.config_name not in {
        "Agent-None-PlainRAG", "Agent-SimplePlanner"
    }:
        return
    manifest = record.manifest or {}
    required = {
        "agent_mode": manifest.get("agent_mode"),
        "agent_enabled": manifest.get("agent_enabled"),
        "agent_version": manifest.get("agent_version"),
        "trace_schema_version": manifest.get("trace_schema_version"),
        "tool_contract_version": manifest.get("tool_contract_version"),
        "generation_provider": _generation_value(manifest, "provider"),
        "generation_model": _generation_value(manifest, "model"),
        "prompt_template_hash": manifest.get("prompt_template_hash"),
        "index_version": manifest.get("index_version"),
        "seed": manifest.get("seed"),
    }
    if record.config_name == "Agent-SimplePlanner":
        required.update({
            "planner_policy": manifest.get("planner_policy"),
            "planner_policy_version": manifest.get("planner_policy_version"),
            "max_steps": manifest.get("max_steps"),
            "max_tool_calls": manifest.get("max_tool_calls"),
            "allowed_tools": manifest.get("allowed_tools"),
        })
    missing = [name for name, value in required.items() if value is None or value == "" or value == []]
    if missing:
        record.validation_errors.append(
            "Completed agent run is missing critical comparison metadata: " + ", ".join(missing) + "."
        )


def _load_completed_artifacts(record: RunRecord) -> None:
    assert record.manifest is not None
    e2e_path = _artifact_path(record, "metrics", "e2e_metrics.json")
    latency_path = _artifact_path(record, "latency", "latency.json")
    e2e = _load_json_object(e2e_path, "E2E metrics", record, required=True)
    latency = _load_json_object(latency_path, "latency", record, required=True)

    if e2e is not None:
        overall = e2e.get("overall")
        if not isinstance(overall, dict):
            record.validation_errors.append("E2E metrics field 'overall' must be an object.")
        else:
            for source, target in (
                ("exact_match", "exact_match"),
                ("token_f1", "token_f1"),
                ("rouge_l", "rouge_l"),
                ("unanswerable_accuracy", "unanswerable_accuracy"),
                ("context_recall@k", "context_recall_at_k"),
            ):
                _extract_number(overall, source, record, target, "E2E metrics")
            for k in (1, 5, 10):
                _extract_number(
                    overall, f"recall@{k}", record, f"recall_at_{k}", "E2E metrics", optional=True
                )
            _extract_rank_metric(overall, "mrr", record)
            _extract_rank_metric(overall, "ndcg", record)
        counts = e2e.get("counts")
        if counts is not None and not isinstance(counts, dict):
            record.validation_errors.append("E2E metrics field 'counts' must be an object.")
        agent_metrics = e2e.get("agent_metrics")
        if isinstance(agent_metrics, dict):
            for key in (
                "tool_call_success_rate", "retrieval_invocation_rate", "average_tool_calls_per_case",
                "planner_abstention_rate", "step_limit_failure_rate", "empty_context_rate", "agent_failure_rate",
            ):
                _extract_number(agent_metrics, key, record, key, "agent metrics")
        citation_metrics = e2e.get("citation_metrics")
        if isinstance(citation_metrics, dict):
            for key in (
                "citation_validity_rate", "average_structural_citation_coverage",
                "average_unique_cited_sources", "cases_with_invalid_citations",
                "cases_with_no_valid_citation",
            ):
                _extract_number(citation_metrics, key, record, key, "citation metrics")

    if latency is not None:
        stages = latency.get("stages")
        if not isinstance(stages, dict):
            record.validation_errors.append("Latency field 'stages' must be an object.")
        else:
            _extract_latency(stages, record)

    retrieval_path = _artifact_path(record, "retrieval_metrics", "retrieval_metrics.json")
    if retrieval_path.is_file():
        retrieval = _load_json_object(retrieval_path, "retrieval metrics", record, required=False)
        if retrieval is not None:
            overall = retrieval.get("overall")
            if not isinstance(overall, dict):
                record.notes.append("Invalid optional retrieval metrics: 'overall' is not an object.")
            else:
                for k in (1, 5, 10):
                    _extract_number(
                        overall, f"recall@{k}", record, f"recall_at_{k}", "retrieval metrics", optional=True
                    )
                _extract_rank_metric(overall, "mrr", record)
                _extract_rank_metric(overall, "ndcg", record)
    else:
        if not any(key in record.metrics for key in ("recall_at_1", "recall_at_5", "recall_at_10", "mrr", "ndcg")):
            record.notes.append("Optional retrieval metrics artifact is unavailable.")

    missing_e2e = [
        target
        for target in (
            "exact_match",
            "token_f1",
            "rouge_l",
            "unanswerable_accuracy",
            "context_recall_at_k",
        )
        if target not in record.metrics
    ]
    if missing_e2e:
        record.notes.append("Unavailable optional E2E fields: " + ", ".join(missing_e2e) + ".")
    missing_stages = [
        stage for stage in LATENCY_STAGES if f"{stage}_mean" not in record.metrics
    ]
    if missing_stages:
        record.notes.append("Unavailable latency stages: " + ", ".join(missing_stages) + ".")


def _validate_supporting_artifacts(record: RunRecord) -> None:
    """Validate artifacts that complete the runner contract but are not aggregated."""

    resolved_config = _artifact_path(record, "resolved_config", "resolved_config.yaml")
    if not resolved_config.is_file():
        record.validation_errors.append("Resolved configuration artifact is missing: resolved_config.yaml.")
    if record.status != "completed":
        return
    for artifact_key, filename, label in (
        ("predictions", "e2e_predictions.jsonl", "E2E predictions"),
        ("errors", "errors.jsonl", "error"),
        ("report", "report.md", "run report"),
    ):
        path = _artifact_path(record, artifact_key, filename)
        if not path.is_file():
            record.validation_errors.append(f"{label.capitalize()} artifact is missing: {filename}.")
            continue
        if path.suffix == ".jsonl":
            _validate_jsonl(path, label, record)


def _validate_jsonl(path: Path, label: str, record: RunRecord) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        record.validation_errors.append(f"Unable to read {label} artifact {path.name}: {_safe_error(exc)}")
        return
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            record.validation_errors.append(
                f"Malformed {label} artifact {path.name} at line {line_number}: {_safe_error(exc)}"
            )
            return
        if not isinstance(value, dict):
            record.validation_errors.append(
                f"{label.capitalize()} artifact {path.name} line {line_number} must be a JSON object."
            )
            return


def _artifact_path(record: RunRecord, artifact_key: str, default_name: str) -> Path:
    assert record.manifest is not None
    artifacts = record.manifest.get("output_artifacts")
    value = artifacts.get(artifact_key) if isinstance(artifacts, dict) else None
    if isinstance(value, str) and value:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = record.directory / candidate
        if candidate.is_file():
            return candidate
    return record.directory / default_name


def _load_json_object(
    path: Path,
    label: str,
    record: RunRecord,
    *,
    required: bool,
) -> dict[str, Any] | None:
    if not path.is_file():
        message = f"{label.capitalize()} artifact is missing: {path.name}."
        (record.validation_errors if required else record.notes).append(message)
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"Malformed {label} artifact {path.name}: {_safe_error(exc)}"
        (record.validation_errors if required else record.notes).append(message)
        return None
    if not isinstance(payload, dict):
        message = f"{label.capitalize()} artifact {path.name} must contain a JSON object."
        (record.validation_errors if required else record.notes).append(message)
        return None
    return payload


def _extract_number(
    source: Mapping[str, Any],
    key: str,
    record: RunRecord,
    target: str,
    label: str,
    *,
    optional: bool = True,
) -> None:
    if key not in source or source[key] is None:
        return
    value = source[key]
    if _is_number(value):
        record.metrics[target] = value
    else:
        message = f"Invalid {label} value for {key!r}; expected a finite number or null."
        (record.notes if optional else record.validation_errors).append(message)


def _extract_rank_metric(overall: Mapping[str, Any], base: str, record: RunRecord) -> None:
    candidates: list[tuple[int, str]] = []
    if base in overall:
        candidates.append((10_000, base))
    for key in overall:
        prefix = f"{base}@"
        if key.startswith(prefix) and key[len(prefix) :].isdigit():
            candidates.append((int(key[len(prefix) :]), key))
    if not candidates:
        return
    preferred = next((item for item in candidates if item[0] == 10), max(candidates))
    _extract_number(overall, preferred[1], record, base, "retrieval metrics", optional=True)


def _extract_latency(stages: Mapping[str, Any], record: RunRecord) -> None:
    for stage in LATENCY_STAGES:
        distribution = stages.get(stage)
        if distribution is None:
            continue
        if not isinstance(distribution, dict):
            record.notes.append(f"Invalid latency stage {stage!r}; expected an object or null.")
            continue
        for statistic in ("mean", "median", "p95"):
            if statistic not in distribution or distribution[statistic] is None:
                continue
            value = distribution[statistic]
            if _is_number(value):
                record.metrics[f"{stage}_{statistic}"] = value
            else:
                record.notes.append(
                    f"Invalid latency value for {stage}.{statistic}; expected a finite number or null."
                )


def _compatibility_key(record: RunRecord) -> tuple[str, ...] | None:
    if record.manifest is None:
        return None
    manifest = record.manifest
    benchmark_name = _dataset_name(manifest, "benchmark")
    corpus_name = _dataset_name(manifest, "corpus")
    benchmark_version = _string(manifest.get("benchmark_version"))
    corpus_version = _string(manifest.get("corpus_version"))
    if not all((benchmark_name, benchmark_version, corpus_name, corpus_version)):
        return None
    schema = _string(
        manifest.get("evaluation_schema_version")
        or _nested(manifest, "resolved_config", "evaluation", "schema_version")
    )
    return (
        benchmark_name,
        benchmark_version,
        corpus_name,
        corpus_version,
        schema,
        _string(manifest.get("index_version")),
        _string(manifest.get("graph_version")),
    )


def detect_duplicates_and_collisions(records: Sequence[RunRecord]) -> None:
    """Annotate all identity duplicates and likely completed-run collisions."""

    by_run_id: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        if record.manifest is not None and record.run_id:
            by_run_id[record.run_id].append(record)
    for run_id, duplicates in sorted(by_run_id.items()):
        if len(duplicates) > 1:
            directories = ", ".join(sorted(item.directory.name for item in duplicates))
            for record in duplicates:
                record.validation_errors.append(
                    f"Duplicate run_id {run_id!r} claimed by directories: {directories}."
                )

    by_identity: dict[tuple[str, tuple[str, ...] | None], list[RunRecord]] = defaultdict(list)
    for record in records:
        if record.status == "completed" and record.config_hash:
            by_identity[(record.config_hash, record.compatible_key)].append(record)
    for (config_hash, _), collisions in sorted(by_identity.items(), key=lambda item: str(item[0])):
        if len(collisions) > 1:
            run_ids = ", ".join(sorted(item.run_id for item in collisions))
            for record in collisions:
                record.notes.append(
                    f"Config collision: hash {config_hash!r} has multiple completed runs ({run_ids})."
                )

    by_name: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        if record.config_name and record.compatible_key:
            by_name[record.config_name].append(record)
    for config_name, reused in sorted(by_name.items()):
        if len({record.compatible_key for record in reused}) > 1:
            for record in reused:
                record.notes.append(
                    f"Config name {config_name!r} is reused across incompatible benchmark/corpus identities."
                )


def select_compatibility_group(records: Sequence[RunRecord]) -> tuple[str, ...] | None:
    """Select the largest completed valid group, breaking ties by identity."""

    candidates = [
        record.compatible_key
        for record in records
        if record.status == "completed" and record.valid and record.compatible_key is not None
    ]
    if not candidates:
        return None
    counts = Counter(candidates)
    return min(counts, key=lambda key: (-counts[key], key))


def classify_comparison_eligibility(
    records: Sequence[RunRecord], selected_group: tuple[str, ...] | None
) -> None:
    for record in records:
        reasons: list[str] = []
        if record.status != "completed":
            reasons.append(f"status is {record.status}")
        if record.validation_errors:
            reasons.append("validation failed")
        if record.compatible_key is None:
            reasons.append("compatibility identity is incomplete")
        elif selected_group is None:
            reasons.append("no valid completed compatibility group exists")
        elif record.compatible_key != selected_group:
            reasons.append("benchmark/corpus experiment identity differs from the selected group")
        record.eligible_for_comparison = not reasons
        record.exclusion_reason = "; ".join(dict.fromkeys(reasons))


def aggregate_ablation_results(
    runs_dir: Path,
    *,
    output_csv: Path | None = None,
    output_report: Path | None = None,
) -> AggregationResult:
    """Aggregate all discovered ablation runs and write CSV/Markdown outputs.

    Individual bad runs are recorded in the outputs and do not make aggregation
    fail. Missing/invalid ``runs_dir`` or an unwritable output is fatal.
    """

    runs_dir = runs_dir.resolve()
    run_dirs = discover_run_directories(runs_dir)
    records = [load_run(path) for path in run_dirs]
    detect_duplicates_and_collisions(records)
    selected = select_compatibility_group(records)
    classify_comparison_eligibility(records, selected)
    records.sort(key=_run_sort_key)

    csv_path = (output_csv or runs_dir / SUMMARY_NAME).resolve()
    report_path = (output_report or runs_dir / REPORT_NAME).resolve()
    _validate_output_paths(csv_path, report_path, records)
    csv_text = render_csv(records, runs_dir)
    report_text = render_report(records, runs_dir, selected)
    _atomic_write_text(csv_path, csv_text)
    _atomic_write_text(report_path, report_text)
    return AggregationResult(tuple(records), csv_path, report_path, selected)


def _validate_output_paths(
    csv_path: Path,
    report_path: Path,
    records: Sequence[RunRecord],
) -> None:
    if csv_path == report_path:
        raise AggregationError("CSV and Markdown output paths must be different.")
    protected = {record.manifest_path.resolve() for record in records}
    for record in records:
        if record.manifest is None:
            continue
        artifacts = record.manifest.get("output_artifacts")
        if not isinstance(artifacts, dict):
            continue
        for key, default_name in (
            ("resolved_config", "resolved_config.yaml"),
            ("predictions", "e2e_predictions.jsonl"),
            ("metrics", "e2e_metrics.json"),
            ("latency", "latency.json"),
            ("errors", "errors.jsonl"),
            ("report", "report.md"),
        ):
            protected.add(_artifact_path(record, key, default_name).resolve())
    for label, path in (("CSV", csv_path), ("Markdown", report_path)):
        if path in protected:
            raise AggregationError(
                f"{label} output path would overwrite a discovered run artifact: {path}"
            )


def render_csv(records: Sequence[RunRecord], runs_dir: Path) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(_csv_row(record, runs_dir))
    return buffer.getvalue()


def _csv_row(record: RunRecord, runs_dir: Path) -> dict[str, Any]:
    manifest = record.manifest or {}
    row: dict[str, Any] = {column: "" for column in CSV_COLUMNS}
    row.update(
        {
            "run_id": record.run_id,
            "config_name": record.config_name,
            "config_hash": record.config_hash,
            "generation_provider": _string(_generation_value(manifest, "provider")),
            "generation_model": _string(_generation_value(manifest, "model")),
            "prompt_strategy": _string(_generation_value(manifest, "prompt_strategy")),
            "prompt_template_version": _string(
                _generation_value(manifest, "prompt_template_version")
            ),
            "prompt_template_hash": _string(manifest.get("prompt_template_hash")),
            "temperature": _optional_number(_decoding_value(manifest, "temperature")),
            "top_p": _optional_number(_decoding_value(manifest, "top_p")),
            "max_output_tokens": _optional_number(
                _decoding_value(manifest, "max_output_tokens")
            ),
            "timeout_seconds": _optional_number(
                _decoding_value(manifest, "timeout_seconds")
            ),
            "max_retries": _optional_number(_decoding_value(manifest, "max_retries")),
            "agent_mode": _string(manifest.get("agent_mode") or _nested(manifest, "resolved_config", "agent", "mode")),
            "agent_version": _string(manifest.get("agent_version")),
            "planner_policy": _string(manifest.get("planner_policy")),
            "max_steps": _optional_number(manifest.get("max_steps")),
            "max_tool_calls": _optional_number(manifest.get("max_tool_calls")),
            "allowed_tools": "|".join(str(value) for value in manifest.get("allowed_tools", []))
            if isinstance(manifest.get("allowed_tools"), list) else "",
            "status": record.status,
            "eligible_for_comparison": str(record.eligible_for_comparison).lower(),
            "exclusion_reason": record.exclusion_reason,
            "benchmark_name": _dataset_name(manifest, "benchmark"),
            "benchmark_version": _string(manifest.get("benchmark_version")),
            "corpus_name": _dataset_name(manifest, "corpus"),
            "corpus_version": _string(manifest.get("corpus_version")),
            "evaluation_schema_version": _string(
                manifest.get("evaluation_schema_version")
                or _nested(manifest, "resolved_config", "evaluation", "schema_version")
            ),
            "index_version": _string(manifest.get("index_version")),
            "graph_version": _string(manifest.get("graph_version")),
            "created_at": _string(manifest.get("start_time")),
            "completed_at": _string(manifest.get("end_time")),
            "git_commit": _string(manifest.get("git_commit")),
            "exact_match": _metric(record, "exact_match"),
            "token_f1": _metric(record, "token_f1"),
            "rouge_l": _metric(record, "rouge_l"),
            "unanswerable_accuracy": _metric(record, "unanswerable_accuracy"),
            "context_recall_at_k": _metric(record, "context_recall_at_k"),
            "recall_at_1": _metric(record, "recall_at_1"),
            "recall_at_5": _metric(record, "recall_at_5"),
            "recall_at_10": _metric(record, "recall_at_10"),
            "mrr": _metric(record, "mrr"),
            "ndcg": _metric(record, "ndcg"),
            "average_total_latency_ms": _metric(record, "total_mean"),
            "median_total_latency_ms": _metric(record, "total_median"),
            "p95_total_latency_ms": _metric(record, "total_p95"),
            "average_planner_latency_ms": _metric(record, "planner_decision_mean"),
            "average_tool_retrieval_latency_ms": _metric(record, "tool_retrieval_mean"),
            "average_agent_total_latency_ms": _metric(record, "agent_total_mean"),
            "successful_cases": _manifest_count(manifest, "completed_case_count"),
            "failed_cases": _manifest_count(manifest, "failed_case_count"),
            "skipped_cases": _manifest_count(manifest, "skipped_case_count"),
            "deferred_cases": _manifest_count(manifest, "deferred_case_count"),
            "notes": " ".join([*record.validation_errors, *record.notes]),
            "run_directory": _display_path(record.directory, runs_dir),
        }
    )
    for stage in LATENCY_STAGES:
        if stage in {"total", "planner_decision", "tool_retrieval", "agent_total"}:
            continue
        row[f"{stage}_latency_ms"] = _metric(record, f"{stage}_mean")
    for key in (
        "tool_call_success_rate", "retrieval_invocation_rate", "average_tool_calls_per_case",
        "planner_abstention_rate", "step_limit_failure_rate", "empty_context_rate", "agent_failure_rate",
        "citation_validity_rate", "average_structural_citation_coverage",
        "average_unique_cited_sources", "cases_with_invalid_citations", "cases_with_no_valid_citation",
    ):
        row[key] = _metric(record, key)
    return row


def render_report(
    records: Sequence[RunRecord],
    runs_dir: Path,
    selected_group: tuple[str, ...] | None,
) -> str:
    status_counts = Counter(record.status for record in records)
    valid_count = sum(record.valid for record in records)
    invalid_count = sum(not record.valid or record.status == "validation-error" for record in records)
    lines = [
        "# Ablation Results Report",
        "",
        "## Aggregation Scope",
        "",
        f"- Runs directory: `{runs_dir.as_posix()}`",
        f"- Discovered runs: {len(records)}",
        f"- Valid runs: {valid_count}",
        f"- Completed: {status_counts['completed']}",
        f"- Failed: {status_counts['failed']}",
        f"- Skipped: {status_counts['skipped']}",
        f"- Deferred: {status_counts['deferred']}",
        f"- Partial: {sum(status_counts[status] for status in PARTIAL_STATUSES)}",
        f"- Invalid: {invalid_count}",
        "",
        "## Compatibility Selection",
        "",
    ]
    if selected_group is None:
        lines.append("No valid completed compatibility group could be selected.")
    else:
        labels = (
            "benchmark",
            "benchmark version",
            "corpus",
            "corpus version",
            "evaluation schema",
            "index version",
            "graph version",
        )
        lines.append(
            "- Selected group: "
            + ", ".join(f"{label}=`{value or 'unspecified'}`" for label, value in zip(labels, selected_group))
        )
    lines.extend(
        [
            "- Rule: select the compatibility identity with the most valid completed runs; ties are resolved by the "
            "lexicographically smallest full identity.",
            "- Direct quality comparison requires matching benchmark name/version, corpus name/version, evaluation "
            "schema, index version, and graph version.",
            "- Non-completed, invalid, incomplete, and incompatible runs remain visible but are excluded.",
            "",
            "## Eligible Run Comparison",
            "",
        ]
    )
    eligible = [record for record in records if record.eligible_for_comparison]
    lines.extend(
        _markdown_table(
            ["Run ID", "Config", "Token F1", "Exact Match", "Recall@5", "Avg total ms"],
            [
                [
                    record.run_id,
                    record.config_name,
                    _format_metric(record, "token_f1"),
                    _format_metric(record, "exact_match"),
                    _format_metric(record, "recall_at_5"),
                    _format_metric(record, "total_mean"),
                ]
                for record in eligible
            ],
        )
    )
    lines.extend(["", "## Excluded or Incompatible Runs", ""])
    excluded = [
        record
        for record in records
        if not record.eligible_for_comparison and record.status == "completed" and record.valid
    ]
    lines.extend(
        _markdown_table(
            ["Run ID", "Config", "Reason"],
            [[record.run_id, record.config_name, record.exclusion_reason] for record in excluded],
        )
    )
    agent_eligible = [
        record for record in eligible
        if _string((record.manifest or {}).get("agent_mode")) in {"none", "simple_planner"}
    ]
    if agent_eligible:
        lines.extend(["", "## Agent Comparison", ""])
        lines.extend(_markdown_table(
            ["Run ID", "Mode", "Token F1", "Tool success", "Retrieval rate", "Abstention rate", "Agent total ms"],
            [[
                record.run_id, _string((record.manifest or {}).get("agent_mode")),
                _format_metric(record, "token_f1"), _format_metric(record, "tool_call_success_rate"),
                _format_metric(record, "retrieval_invocation_rate"), _format_metric(record, "planner_abstention_rate"),
                _format_metric(record, "agent_total_mean"),
            ] for record in agent_eligible],
        ))
        lines.extend(["", "Agent mode is the ablation dimension; this section reports observed values only and does not select a best agent."])
    lines.extend(["", "## Non-completed and Invalid Runs", ""])
    diagnostic = [
        record
        for record in records
        if record.status != "completed" or not record.valid
    ]
    lines.extend(
        _markdown_table(
            ["Run ID", "Config", "Status", "Details"],
            [
                [
                    record.run_id,
                    record.config_name or "N/A",
                    record.status,
                    " ".join([record.exclusion_reason, *record.validation_errors, *record.notes]).strip(),
                ]
                for record in diagnostic
            ],
        )
    )
    lines.extend(["", "## Artifact and Identity Warnings", ""])
    warnings = [
        (record.run_id, note)
        for record in records
        for note in [*record.validation_errors, *record.notes]
        if any(
            marker in note.lower()
            for marker in ("missing", "malformed", "unavailable", "invalid", "duplicate", "collision", "reused")
        )
    ]
    if warnings:
        lines.extend(f"- `{_md(run_id)}`: {_md(note)}" for run_id, note in warnings)
    else:
        lines.append("No artifact or identity warnings.")
    lines.extend(["", "## Quality-versus-Latency Observations", ""])
    lines.extend(_observations(eligible))
    lines.extend(
        [
            "",
            "## Recommendation Boundary",
            "",
            "The manifests do not encode the complete planned experiment-family matrix. No best pipeline "
            "recommendation can be finalized when required experiment families are missing; confirm matrix "
            "completeness and inspect the comparable production runs before drawing a scientific conclusion.",
            "",
        ]
    )
    return "\n".join(lines)


def _observations(eligible: Sequence[RunRecord]) -> list[str]:
    observations: list[str] = []
    quality = [
        (record, value)
        for record in eligible
        if (value := _metric_value(record, "token_f1")) is not None
    ]
    latency = [
        (record, value)
        for record in eligible
        if (value := _metric_value(record, "total_mean")) is not None
    ]
    if quality:
        highest = max(value for _, value in quality)
        winners = ", ".join(record.run_id for record, value in quality if value == highest)
        observations.append(f"- Highest available Token F1: {highest:.6g} ({winners}).")
    if latency:
        lowest = min(value for _, value in latency)
        winners = ", ".join(record.run_id for record, value in latency if value == lowest)
        observations.append(f"- Lowest average total latency: {lowest:.6g} ms ({winners}).")
    paired = [
        (record, quality_value, latency_value)
        for record in eligible
        if (quality_value := _metric_value(record, "token_f1")) is not None
        and (latency_value := _metric_value(record, "total_mean")) is not None
    ]
    if paired:
        pareto = [
            candidate_record
            for candidate_record, candidate_quality, candidate_latency in paired
            if not any(
                other_record is not candidate_record
                and other_quality >= candidate_quality
                and other_latency <= candidate_latency
                and (
                    other_quality > candidate_quality
                    or other_latency < candidate_latency
                )
                for other_record, other_quality, other_latency in paired
            )
        ]
        observations.append("- Token-F1/average-latency Pareto candidates: " + ", ".join(r.run_id for r in pareto) + ".")
    if not observations:
        observations.append("No data-derived quality-versus-latency observation is available.")
    return observations


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    if not rows:
        return ["No runs in this section."]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_md(value) for value in row) + " |" for row in rows)
    return lines


def _dataset_name(manifest: Mapping[str, Any], prefix: str) -> str:
    explicit = manifest.get(f"{prefix}_name")
    if _string(explicit):
        return _string(explicit)
    configured = _nested(manifest, "resolved_config", prefix, "name")
    if _string(configured):
        return _string(configured)
    path_value = _string(manifest.get(f"{prefix}_path"))
    return Path(path_value).stem if path_value else ""


def _nested(source: Mapping[str, Any], *keys: str) -> Any:
    value: Any = source
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _generation_value(manifest: Mapping[str, Any], key: str) -> Any:
    top_level_names = {
        "provider": "generation_provider",
        "model": "generation_model",
    }
    top_level = manifest.get(top_level_names.get(key, key))
    if top_level is not None:
        return top_level
    return _nested(manifest, "resolved_config", "generation", key)


def _decoding_value(manifest: Mapping[str, Any], key: str) -> Any:
    value = _nested(manifest, "generation_decoding", key)
    if value is not None:
        return value
    return _nested(manifest, "resolved_config", "generation", key)


def _run_sort_key(record: RunRecord) -> tuple[str, str, str]:
    return (record.run_id.casefold(), record.config_name.casefold(), record.directory.as_posix().casefold())


def _manifest_count(manifest: Mapping[str, Any], key: str) -> int | str:
    value = manifest.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else ""


def _metric(record: RunRecord, key: str) -> float | int | str:
    value = record.metrics.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return value
    return ""


def _optional_number(value: Any) -> float | int | str:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return value
    return ""


def _metric_value(record: RunRecord, key: str) -> float | None:
    value = record.metrics.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    return None


def _format_metric(record: RunRecord, key: str) -> str:
    value = _metric_value(record, key)
    return "N/A" if value is None else f"{value:.6g}"


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return f"JSON decode error at line {exc.lineno}, column {exc.colno}."
    return type(exc).__name__


def _display_path(path: Path, runs_dir: Path) -> str:
    try:
        return path.resolve().relative_to(runs_dir.resolve()).as_posix() or "."
    except ValueError:
        return path.resolve().as_posix()


def _md(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise AggregationError(f"Unable to write aggregate output {path}: {type(exc).__name__}") from exc


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate ablation run manifests and write deterministic CSV and Markdown comparisons."
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help=f"Directory containing ablation runs (default: {DEFAULT_RUNS_DIR}).",
    )
    parser.add_argument("--output-csv", type=Path, default=None, help=f"CSV output path (default: RUNS_DIR/{SUMMARY_NAME}).")
    parser.add_argument(
        "--output-report",
        type=Path,
        default=None,
        help=f"Markdown output path (default: RUNS_DIR/{REPORT_NAME}).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = aggregate_ablation_results(
            args.runs_dir,
            output_csv=args.output_csv,
            output_report=args.output_report,
        )
    except AggregationError as exc:
        print(f"Aggregation error: {exc}", file=sys.stderr)
        return 2
    print(f"Discovered runs: {result.discovered_count}")
    print(f"Comparable runs: {result.comparable_count}")
    print(f"Excluded runs: {result.excluded_count}")
    print(f"Invalid runs: {result.invalid_count}")
    print(f"CSV: {result.output_csv}")
    print(f"Markdown: {result.output_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
