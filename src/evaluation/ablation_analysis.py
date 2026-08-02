"""Deterministic, aggregate-only analysis helpers for ablation reports.

The helpers in this module never inspect individual run artifacts.  The canonical
``ablation_summary.csv`` produced by ``scripts/aggregate_ablation_results.py`` is
the sole source of metrics, eligibility, and compatibility decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
import zipfile

import pandas as pd


FAMILIES = ("retrieval", "embedding", "reranker", "graph", "llm", "agent", "unclassified")
REQUIRED_COLUMNS = (
    "run_id",
    "config_name",
    "status",
    "eligible_for_comparison",
    "exclusion_reason",
    "benchmark_name",
    "benchmark_version",
    "corpus_name",
    "corpus_version",
)
COMPATIBILITY_COLUMNS = (
    "benchmark_name",
    "benchmark_version",
    "corpus_name",
    "corpus_version",
    "evaluation_schema_version",
    "index_version",
    "graph_version",
)
NUMERIC_COLUMNS = (
    "exact_match", "token_f1", "rouge_l", "unanswerable_accuracy",
    "context_recall_at_k", "recall_at_1", "recall_at_5", "recall_at_10",
    "mrr", "ndcg", "average_total_latency_ms", "median_total_latency_ms",
    "p95_total_latency_ms", "dense_retrieval_latency_ms",
    "sparse_retrieval_latency_ms", "graph_traversal_latency_ms",
    "fusion_latency_ms", "reranker_latency_ms", "generation_latency_ms",
    "judge_latency_ms", "serialization_latency_ms", "average_planner_latency_ms",
    "average_tool_retrieval_latency_ms", "average_agent_total_latency_ms",
    "tool_call_success_rate", "retrieval_invocation_rate",
    "average_tool_calls_per_case", "planner_abstention_rate",
    "step_limit_failure_rate", "empty_context_rate", "agent_failure_rate",
    "successful_cases", "failed_cases", "skipped_cases", "deferred_cases",
)
KNOWN_FAMILIES = {
    "Retrieval-DenseOnly": "retrieval",
    "Retrieval-Hybrid-SparseDense": "retrieval",
    "Embed-ChunkOnly-Dense": "embedding",
    "Embed-ChunkMeta-Dense": "embedding",
    "Rerank-None-Hybrid": "reranker",
    "Rerank-RRF-Hybrid": "reranker",
    "Rerank-CrossEncoder-Hybrid": "reranker",
    "Rerank-RRFPlusCrossEncoder-Hybrid": "reranker",
    "Retrieval-Dense-Graph": "graph",
    "Retrieval-Hybrid-SparseDense-Graph": "graph",
    "LLM-BaseReasoning": "llm",
    "LLM-StrongReasoning": "llm",
    "LLM-AlternativeReasoning": "llm",
    "Agent-None-PlainRAG": "agent",
    "Agent-SimplePlanner": "agent",
    "Agent-MultiTool": "agent",
}
BASELINES = {"llm": "LLM-BaseReasoning", "agent": "Agent-None-PlainRAG"}
RECOMMENDATION_BOUNDARY = (
    "A final main-pipeline recommendation cannot be finalized until all required "
    "experiment families have valid comparable runs and the selected candidate is "
    "verified in the UI."
)

FAMILY_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "retrieval": ("config_name", "status", "eligible_for_comparison", "recall_at_1", "recall_at_5", "recall_at_10", "mrr", "ndcg", "context_recall_at_k", "average_total_latency_ms", "median_total_latency_ms", "notes"),
    "embedding": ("config_name", "generation_model", "status", "eligible_for_comparison", "exact_match", "token_f1", "rouge_l", "context_recall_at_k", "recall_at_5", "mrr", "ndcg", "average_total_latency_ms", "notes"),
    "reranker": ("config_name", "status", "eligible_for_comparison", "recall_at_5", "mrr", "ndcg", "context_recall_at_k", "token_f1", "rouge_l", "reranker_latency_ms", "average_total_latency_ms", "notes"),
    "graph": ("config_name", "graph_version", "status", "eligible_for_comparison", "recall_at_5", "mrr", "ndcg", "context_recall_at_k", "token_f1", "rouge_l", "graph_traversal_latency_ms", "average_total_latency_ms", "notes"),
    "llm": ("config_name", "generation_model", "prompt_strategy", "prompt_template_version", "prompt_template_hash", "exact_match", "token_f1", "rouge_l", "unanswerable_accuracy", "generation_latency_ms", "average_total_latency_ms", "failed_cases", "status", "eligible_for_comparison", "notes"),
    "agent": ("config_name", "agent_mode", "planner_policy", "allowed_tools", "token_f1", "rouge_l", "context_recall_at_k", "tool_call_success_rate", "retrieval_invocation_rate", "planner_abstention_rate", "agent_failure_rate", "average_planner_latency_ms", "average_agent_total_latency_ms", "status", "eligible_for_comparison", "notes"),
    "unclassified": ("run_id", "config_name", "status", "eligible_for_comparison", "exclusion_reason", "notes"),
}


class AblationAnalysisError(ValueError):
    """Raised when an aggregate artifact cannot be safely analyzed."""


@dataclass(frozen=True)
class SummaryValidation:
    missing_required_columns: tuple[str, ...]
    invalid_boolean_rows: tuple[int, ...]
    invalid_numeric_cells: tuple[str, ...]
    duplicate_run_ids: tuple[str, ...]
    duplicate_row_count: int
    compatibility_group_count: int
    eligible_row_count: int

    @property
    def is_valid(self) -> bool:
        return not self.missing_required_columns and not self.invalid_boolean_rows

    def messages(self) -> list[str]:
        messages: list[str] = []
        if self.missing_required_columns:
            messages.append("Missing required columns: " + ", ".join(self.missing_required_columns))
        if self.invalid_boolean_rows:
            messages.append("Invalid eligible_for_comparison values at source rows: " + ", ".join(map(str, self.invalid_boolean_rows)))
        if self.invalid_numeric_cells:
            messages.append("Invalid numeric cells preserved as missing: " + ", ".join(self.invalid_numeric_cells))
        if self.duplicate_run_ids:
            messages.append("Duplicate run_id values: " + ", ".join(self.duplicate_run_ids))
        if self.duplicate_row_count:
            messages.append(f"Duplicate rows: {self.duplicate_row_count}")
        if self.compatibility_group_count > 1:
            messages.append(f"Multiple benchmark/corpus compatibility groups: {self.compatibility_group_count}")
        if self.eligible_row_count == 0:
            messages.append("No eligible comparison rows are available.")
        return messages


@dataclass(frozen=True)
class SummaryData:
    frame: pd.DataFrame
    validation: SummaryValidation


def _parse_eligible(value: object) -> object:
    if pd.isna(value) or str(value).strip() == "":
        return pd.NA
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return pd.NA


def load_ablation_summary(path: str | Path) -> SummaryData:
    """Load and validate a canonical aggregate CSV without discarding rows."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Aggregate CSV not found: {source}")
    try:
        raw = pd.read_csv(source, dtype="string", keep_default_na=True)
    except Exception as exc:
        raise AblationAnalysisError(f"Could not parse aggregate CSV {source}: {exc}") from exc
    frame = raw.copy()
    missing = tuple(column for column in REQUIRED_COLUMNS if column not in frame.columns)
    invalid_boolean_rows: list[int] = []
    if "eligible_for_comparison" in frame:
        original = frame["eligible_for_comparison"]
        parsed = original.map(_parse_eligible).astype("boolean")
        invalid = original.notna() & original.astype("string").str.strip().ne("") & parsed.isna()
        invalid_boolean_rows = [int(index) + 2 for index in frame.index[invalid]]
        frame["eligible_for_comparison"] = parsed
    invalid_numeric: list[str] = []
    for column in NUMERIC_COLUMNS:
        if column not in frame:
            continue
        original = frame[column]
        converted = pd.to_numeric(original, errors="coerce")
        invalid = original.notna() & original.astype("string").str.strip().ne("") & converted.isna()
        invalid_numeric.extend(f"{column}@{int(index) + 2}" for index in frame.index[invalid])
        frame[column] = converted.astype("Float64")
    duplicate_ids: tuple[str, ...] = ()
    if "run_id" in frame:
        duplicate_ids = tuple(sorted(frame.loc[frame["run_id"].notna() & frame["run_id"].duplicated(keep=False), "run_id"].astype(str).unique()))
    present_compatibility = [column for column in COMPATIBILITY_COLUMNS if column in frame]
    groups = int(frame[present_compatibility].drop_duplicates().shape[0]) if present_compatibility and not frame.empty else 0
    eligible_count = int(frame.get("eligible_for_comparison", pd.Series(dtype="boolean")).fillna(False).sum())
    validation = SummaryValidation(
        missing_required_columns=missing,
        invalid_boolean_rows=tuple(invalid_boolean_rows),
        invalid_numeric_cells=tuple(invalid_numeric),
        duplicate_run_ids=duplicate_ids,
        duplicate_row_count=int(raw.duplicated().sum()),
        compatibility_group_count=groups,
        eligible_row_count=eligible_count,
    )
    return SummaryData(frame=frame, validation=validation)


def _metadata_family(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    candidates: list[object] = [metadata.get("ablation_family"), metadata.get("experiment_family")]
    experiment = metadata.get("experiment")
    if isinstance(experiment, Mapping):
        candidates.append(experiment.get("family"))
    candidates.extend(metadata.get("tags", []) if isinstance(metadata.get("tags"), list) else [])
    aliases = {"llm-reasoning-model": "llm", "agent-orchestration": "agent"}
    for candidate in candidates:
        value = str(candidate).strip().lower() if candidate is not None else ""
        value = aliases.get(value, value)
        if value in FAMILIES[:-1]:
            return value
    return None


def classify_ablation_family(row: Mapping[str, Any], config_metadata: Mapping[str, Any] | None = None) -> str:
    """Classify using explicit CSV/config metadata before exact-name fallbacks."""
    explicit = _metadata_family(row)
    if explicit:
        return explicit
    explicit = _metadata_family(config_metadata)
    if explicit:
        return explicit
    name = str(row.get("config_name", "") or "").strip()
    if name in KNOWN_FAMILIES:
        return KNOWN_FAMILIES[name]
    controlled = (("Retrieval-", "retrieval"), ("Embed-", "embedding"), ("Rerank-", "reranker"), ("Graph-", "graph"), ("LLM-", "llm"), ("Agent-", "agent"))
    for prefix, family in controlled:
        if name.startswith(prefix):
            return family
    return "unclassified"


def classify_summary(frame: pd.DataFrame, config_metadata: Mapping[str, Mapping[str, Any]] | None = None) -> pd.DataFrame:
    result = frame.copy()
    metadata = config_metadata or {}
    result["family"] = [classify_ablation_family(row, metadata.get(str(row.get("config_name", "")))) for row in result.to_dict("records")]
    return result


def select_comparable_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Select rows already marked eligible by the canonical aggregator."""
    required = {"eligible_for_comparison", "status", *COMPATIBILITY_COLUMNS[:4]}
    if not required.issubset(frame.columns):
        return frame.iloc[0:0].copy()
    mask = frame["eligible_for_comparison"].fillna(False).astype(bool) & frame["status"].astype("string").str.lower().eq("completed")
    mask &= frame[list(COMPATIBILITY_COLUMNS[:4])].notna().all(axis=1)
    result = frame.loc[mask].copy()
    return result.sort_values([column for column in ("family", "config_name", "run_id") if column in result], kind="stable").reset_index(drop=True)


def summarize_coverage(frame: pd.DataFrame, expected: Mapping[str, Sequence[str]] | None = None) -> pd.DataFrame:
    status = frame.get("status", pd.Series(index=frame.index, dtype="string")).astype("string").str.lower()
    eligible = frame.get("eligible_for_comparison", pd.Series(False, index=frame.index, dtype="boolean")).fillna(False)
    rows: list[dict[str, object]] = [
        {"scope": "all", "measure": "total_rows", "value": len(frame)},
        {"scope": "all", "measure": "eligible_rows", "value": int(eligible.sum())},
        {"scope": "all", "measure": "excluded_rows", "value": int((~eligible).sum())},
    ]
    status_groups = {
        "completed_rows": {"completed"}, "failed_rows": {"failed"}, "skipped_rows": {"skipped"},
        "deferred_rows": {"deferred"}, "partial_needs_rerun_rows": {"partial", "needs-rerun"},
        "invalid_rows": {"invalid", "validation-error"},
    }
    rows.extend({"scope": "all", "measure": key, "value": int(status.isin(values).sum())} for key, values in status_groups.items())
    compatibility = [column for column in COMPATIBILITY_COLUMNS if column in frame]
    rows.append({"scope": "all", "measure": "compatibility_groups", "value": int(frame[compatibility].drop_duplicates().shape[0]) if compatibility and not frame.empty else 0})
    family_series = frame.get("family", pd.Series("unclassified", index=frame.index))
    for family in FAMILIES:
        available = sorted(frame.loc[family_series.eq(family), "config_name"].dropna().astype(str).unique()) if "config_name" in frame else []
        eligible_completed = int((family_series.eq(family) & eligible & status.eq("completed")).sum())
        expected_names = sorted((expected or {}).get(family, ()))
        missing = [name for name in expected_names if name not in available]
        rows.extend((
            {"scope": family, "measure": "available_config_count", "value": len(available)},
            {"scope": family, "measure": "eligible_completed_rows", "value": eligible_completed},
            {"scope": family, "measure": "expected_configs", "value": "; ".join(expected_names)},
            {"scope": family, "measure": "missing_expected_configs", "value": "; ".join(missing)},
        ))
    return pd.DataFrame(rows, columns=("scope", "measure", "value"))


def build_family_table(frame: pd.DataFrame, family: str, include_ineligible: bool = False) -> pd.DataFrame:
    if family not in FAMILY_COLUMNS:
        raise AblationAnalysisError(f"Unknown family: {family}")
    family_series = frame.get("family", pd.Series("unclassified", index=frame.index))
    subset = frame.loc[family_series.eq(family)].copy()
    if not include_ineligible and "eligible_for_comparison" in subset:
        subset = subset.loc[subset["eligible_for_comparison"].fillna(False)]
    for column in FAMILY_COLUMNS[family]:
        if column not in subset:
            subset[column] = pd.NA
    shaped = subset.loc[:, list(FAMILY_COLUMNS[family])]
    order = [column for column in ("config_name", "run_id") if column in shaped]
    if order:
        shaped = shaped.sort_values(order, kind="stable")
    return shaped.reset_index(drop=True)


def add_baseline_deltas(table: pd.DataFrame, family: str, baseline_name: str | None = None) -> pd.DataFrame:
    """Add absolute display deltas only when an explicit baseline exists."""
    result = table.copy()
    name = baseline_name or BASELINES.get(family)
    if not name or "config_name" not in result or not result["config_name"].eq(name).any():
        return result
    baseline = result.loc[result["config_name"].eq(name)].sort_values("config_name", kind="stable").iloc[0]
    metrics = ("token_f1", "rouge_l", "context_recall_at_k", "average_total_latency_ms", "agent_failure_rate")
    for metric in metrics:
        if metric in result:
            result[f"delta_{metric}_absolute"] = result[metric] - baseline[metric]
    return result


def compute_pareto_frontier(frame: pd.DataFrame, quality_metric: str, latency_metric: str) -> pd.DataFrame:
    comparable = select_comparable_rows(frame)
    if quality_metric not in comparable or latency_metric not in comparable:
        return comparable.iloc[0:0].copy()
    candidates = comparable.loc[comparable[[quality_metric, latency_metric]].notna().all(axis=1)].copy()
    dominated: list[bool] = []
    for _, row in candidates.iterrows():
        other = candidates.drop(index=row.name)
        dominates = (other[quality_metric].ge(row[quality_metric]) & other[latency_metric].le(row[latency_metric]) & (other[quality_metric].gt(row[quality_metric]) | other[latency_metric].lt(row[latency_metric]))).any()
        dominated.append(bool(dominates))
    candidates["pareto_candidate"] = [not value for value in dominated]
    frontier = candidates.loc[candidates["pareto_candidate"]].copy()
    order = [quality_metric, latency_metric] + [column for column in ("config_name", "run_id") if column in frontier]
    ascending = [False, True] + [True] * (len(order) - 2)
    return frontier.sort_values(order, ascending=ascending, kind="stable").reset_index(drop=True)


def diagnostic_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = frame.get("eligible_for_comparison", pd.Series(False, index=frame.index, dtype="boolean")).fillna(False)
    status = frame.get("status", pd.Series(index=frame.index, dtype="string")).astype("string").str.lower()
    present_critical = [column for column in COMPATIBILITY_COLUMNS[:4] if column in frame]
    missing_critical = (
        frame[present_critical].isna().any(axis=1)
        if len(present_critical) == len(COMPATIBILITY_COLUMNS[:4])
        else pd.Series(True, index=frame.index)
    )
    diagnostic_columns = ("run_id", "config_name", "family", "status", "eligible_for_comparison", "exclusion_reason", "notes", "failed_cases", "skipped_cases", "deferred_cases")
    def shaped(mask: pd.Series) -> pd.DataFrame:
        subset = frame.loc[mask].copy()
        for column in diagnostic_columns:
            if column not in subset:
                subset[column] = pd.NA
        return subset.loc[:, diagnostic_columns].sort_values(["status", "config_name", "run_id"], kind="stable").reset_index(drop=True)
    return shaped(~eligible | missing_critical), shaped(status.isin({"failed", "skipped", "deferred", "partial", "needs-rerun", "invalid", "validation-error"}))


def generate_mechanical_observations(frame: pd.DataFrame, quality_metric: str, latency_metric: str, expected_families: Iterable[str] = FAMILIES[:-1]) -> list[str]:
    comparable = select_comparable_rows(frame)
    observations: list[str] = []
    case_text = ""
    if "successful_cases" in comparable and comparable["successful_cases"].notna().any():
        case_text = f" Case count is available (successful cases range {comparable['successful_cases'].min():g}-{comparable['successful_cases'].max():g})."
    if comparable.empty:
        observations.append("No eligible completed runs are available for mechanical comparison.")
    else:
        if quality_metric in comparable and comparable[quality_metric].notna().any():
            row = comparable.sort_values([quality_metric, "config_name"], ascending=[False, True], kind="stable").dropna(subset=[quality_metric]).iloc[0]
            observations.append(f"Highest available {quality_metric}: {row['config_name']} ({row[quality_metric]:g}).{case_text}")
        if latency_metric in comparable and comparable[latency_metric].notna().any():
            row = comparable.sort_values([latency_metric, "config_name"], kind="stable").dropna(subset=[latency_metric]).iloc[0]
            observations.append(f"Lowest available {latency_metric}: {row['config_name']} ({row[latency_metric]:g} ms).{case_text}")
        frontier = compute_pareto_frontier(frame, quality_metric, latency_metric)
        if not frontier.empty:
            observations.append("Mechanical Pareto candidates: " + ", ".join(frontier["config_name"].astype(str)) + ".")
    represented = set(comparable.get("family", pd.Series(dtype="string")).dropna().astype(str))
    missing = [family for family in expected_families if family not in represented]
    if missing:
        observations.append("Families without an eligible completed run: " + ", ".join(missing) + ".")
    deferred = frame.loc[frame.get("status", pd.Series(index=frame.index, dtype="string")).astype("string").str.lower().eq("deferred"), "config_name"] if "config_name" in frame else pd.Series(dtype="string")
    if not deferred.empty:
        observations.append("Deferred configurations remain outside comparison: " + ", ".join(sorted(deferred.dropna().astype(str).unique())) + ".")
    observations.append(RECOMMENDATION_BOUNDARY)
    return observations


def create_quality_latency_plot(frame: pd.DataFrame, quality_metric: str, latency_metric: str, output_path: str | Path, title: str) -> Path | None:
    comparable = select_comparable_rows(frame)
    if quality_metric not in comparable or latency_metric not in comparable:
        return None
    data = comparable.dropna(subset=[quality_metric, latency_metric])
    if len(data) < 2:
        return None
    import matplotlib.pyplot as plt
    destination = Path(output_path)
    figure, axis = plt.subplots()
    axis.scatter(data[latency_metric], data[quality_metric])
    for _, row in data.iterrows():
        axis.annotate(str(row.get("config_name", row.get("run_id", "run"))), (row[latency_metric], row[quality_metric]), xytext=(4, 4), textcoords="offset points")
    axis.set_xlabel(f"{latency_metric} (ms)")
    axis.set_ylabel(quality_metric)
    axis.set_title(title)
    figure.tight_layout()
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def _safe_manifest_value(value: object) -> object:
    text = str(value)
    return re.sub(r"(?i)(token|secret|password|api[_-]?key)=[^&\s]+", r"\1=[REDACTED]", text)


def render_mechanical_markdown(frame: pd.DataFrame, source: str | Path, quality_metric: str, latency_metric: str, expected_families: Iterable[str] = FAMILIES[:-1]) -> str:
    observations = generate_mechanical_observations(frame, quality_metric, latency_metric, expected_families)
    comparable = select_comparable_rows(frame)
    excluded, failed = diagnostic_rows(frame)
    family_counts = frame.get("family", pd.Series(dtype="string")).value_counts().sort_index()
    lines = [
        "# Mechanical Ablation Observations", "", "## Analysis scope", "",
        "This draft mechanically summarizes the canonical aggregate table; it does not establish causality or statistical superiority.", "",
        "## Source aggregate artifact", "", f"- {Path(source).name}", "",
        "## Compatibility group", "", f"- Eligible completed comparison rows: {len(comparable)}", "",
        "## Coverage summary", "", f"- Total rows: {len(frame)}", f"- Excluded rows: {len(excluded)}", "",
        "## Family availability", "",
    ]
    lines.extend(f"- {family}: {int(count)} row(s)" for family, count in family_counts.items())
    lines.extend(["", "## Best observed quality and lowest observed latency", ""])
    lines.extend(f"- {item}" for item in observations if item.startswith(("Highest", "Lowest")))
    lines.extend(["", "## Pareto candidates", ""])
    lines.extend(f"- {item}" for item in observations if "Pareto" in item)
    lines.extend(["", "## Excluded runs", "", f"- {len(excluded)} excluded or ineligible row(s).", "", "## Failed/deferred configs", "", f"- {len(failed)} failed, skipped, deferred, partial, needs-rerun, or invalid row(s).", "", "## Missing experiment families", ""])
    lines.extend(f"- {item}" for item in observations if item.startswith("Families without"))
    lines.extend(["", "## Limitations", "", "- Results are observational and limited to persisted aggregate fields and aggregator eligibility decisions.", "", "## Recommendation boundary", "", RECOMMENDATION_BOUNDARY, ""])
    return "\n".join(lines)


def export_analysis_outputs(
    frame: pd.DataFrame,
    output_root: str | Path,
    source_csv: str | Path,
    repository_commit: str,
    quality_metric: str = "token_f1",
    latency_metric: str = "average_total_latency_ms",
    expected: Mapping[str, Sequence[str]] | None = None,
    create_zip: bool = True,
) -> Path:
    """Export report artifacts to a new collision-safe directory."""
    root = Path(output_root)
    destination = root
    suffix = 1
    while destination.exists() or (create_zip and destination.with_suffix(".zip").exists()):
        destination = root.with_name(f"{root.name}-{suffix}")
        suffix += 1
    destination.mkdir(parents=True)
    summarize_coverage(frame, expected).to_csv(destination / "coverage_summary.csv", index=False)
    for family in FAMILIES[:-1]:
        build_family_table(frame, family, include_ineligible=True).to_csv(destination / f"{family}_ablation_table.csv", index=False)
    compute_pareto_frontier(frame, quality_metric, latency_metric).to_csv(destination / "pareto_candidates.csv", index=False)
    excluded, failed = diagnostic_rows(frame)
    excluded.to_csv(destination / "excluded_runs.csv", index=False)
    failed.to_csv(destination / "failed_deferred_runs.csv", index=False)
    markdown = render_mechanical_markdown(frame, source_csv, quality_metric, latency_metric)
    (destination / "mechanical_observations.md").write_text(markdown, encoding="utf-8")
    plot_specs = (
        (quality_metric, latency_metric, "quality_vs_average_latency.png", "Primary quality versus average latency"),
        (quality_metric, "median_total_latency_ms", "quality_vs_median_latency.png", "Primary quality versus median latency"),
        ("context_recall_at_k", "dense_retrieval_latency_ms", "retrieval_quality_vs_retrieval_latency.png", "Retrieval quality versus retrieval latency"),
        ("token_f1", "generation_latency_ms", "llm_quality_vs_generation_latency.png", "LLM quality versus generation latency"),
        ("token_f1", "average_agent_total_latency_ms", "agent_quality_vs_agent_latency.png", "Agent quality versus agent latency"),
    )
    for quality, latency, filename, title in plot_specs:
        create_quality_latency_plot(frame, quality, latency, destination / filename, title)
    manifest = {
        "source_csv": _safe_manifest_value(source_csv),
        "repository_commit": _safe_manifest_value(repository_commit),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "quality_metric": quality_metric,
        "latency_metric": latency_metric,
        "filters": "eligible_for_comparison=true; status=completed; benchmark/corpus metadata present",
        "comparison_source": "ablation_summary.csv only",
    }
    (destination / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if create_zip:
        archive = destination.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for artifact in sorted(destination.iterdir()):
                bundle.write(artifact, artifact.name)
    return destination


def expected_configs_by_family(configs: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {family: [] for family in FAMILIES[:-1]}
    for name, config in configs.items():
        family = classify_ablation_family({"config_name": name}, config.get("metadata", config))
        if family in result:
            result[family].append(name)
    return {family: sorted(names) for family, names in result.items()}
