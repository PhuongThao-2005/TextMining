"""Shared per-case / per-mode / comparison shapes and report writers for the
retrieval evaluation notebook.

Pure, testable helpers per data-model.md §2.4, §2.6, §2.8-§2.11. Reuses
`src/evaluation/metrics.py` as the sole metric source (no ad-hoc formulas)
and mirrors the table-building pattern from `scripts/evaluate_retrieval.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .io_utils import write_json, write_jsonl
from .metrics import hit_at_k, jaccard_at_k, mrr_at_k, ndcg_at_k, recall_at_k

RetrievalMode = Literal["vector_only", "hybrid"]

METRIC_NAMES = ("recall", "hit", "mrr", "ndcg", "jaccard")


@dataclass(frozen=True)
class HybridDiagnostics:
    """Per-case hybrid participation record (FR-003c)."""

    traversal_mode: str
    traversal_start_ids: tuple[str, ...]
    traversal_visited_count: int
    whitelist_id_strs: tuple[str, ...]
    whitelist_empty: bool
    filtered_vector_seed_chunk_ids: tuple[str, ...]
    expansion_seed_count: int
    expansion_added_count: int
    expansion_empty_added: bool
    extra_traversal_chunk_ids: tuple[str, ...]
    overlays_available: bool
    prepass_empty_start: bool
    hybrid_unavailable_reason: str | None = None


@dataclass(frozen=True)
class RetrievalCaseResult:
    """Per-case score row, unified across vector-only and hybrid modes."""

    qa_id: str
    mode: RetrievalMode
    question: str
    category: str | None
    difficulty: str | None
    answer_type: str | None
    ground_truth_chunk_ids: list[str]
    retrieved_chunk_ids: list[str]
    metrics: dict[str, float]
    hybrid_diagnostics: HybridDiagnostics | None = None
    error: str | None = None


@dataclass(frozen=True)
class ModeRunSummary:
    """Aggregate summary for a single mode's run."""

    mode: RetrievalMode
    config: dict[str, Any]
    total_rows: int
    evaluated: int
    skipped_unanswerable: int
    skipped_missing_ground_truth: int
    error_count: int
    overall: dict[str, Any]
    by_category: dict[str, Any]
    by_difficulty: dict[str, Any]
    by_answer_type: dict[str, Any]
    hybrid_available: bool = True
    hybrid_unavailable_reason: str | None = None


@dataclass(frozen=True)
class ComparisonSummary:
    """Dual-mode comparison, persisted only when both modes ran."""

    shared_top_k: list[int]
    vector_only: ModeRunSummary | None
    hybrid: ModeRunSummary | None
    hybrid_available: bool
    rows: list[dict[str, Any]] = field(default_factory=list)


def metric_keys_for(top_k_list: list[int]) -> list[str]:
    """Return the ordered `metric@k` keys matching `evaluate_retrieval.py`."""

    return [f"{name}@{k}" for k in top_k_list for name in METRIC_NAMES]


def build_case_metrics_row(
    retrieved_chunk_ids: list[str],
    ground_truth_chunk_ids: set[str],
    top_k_list: list[int],
) -> dict[str, float]:
    """Thin wrapper calling `metrics.py` functions per configured k.

    The sole source of retrieval metrics (FR-004, FR-006); `k` values
    greater than `len(retrieved_chunk_ids)` are handled by `metrics.py`
    semantics unchanged.
    """

    row: dict[str, float] = {}
    for k in top_k_list:
        row[f"recall@{k}"] = recall_at_k(retrieved_chunk_ids, ground_truth_chunk_ids, k)
        row[f"hit@{k}"] = hit_at_k(retrieved_chunk_ids, ground_truth_chunk_ids, k)
        row[f"mrr@{k}"] = mrr_at_k(retrieved_chunk_ids, ground_truth_chunk_ids, k)
        row[f"ndcg@{k}"] = ndcg_at_k(retrieved_chunk_ids, ground_truth_chunk_ids, k)
        row[f"jaccard@{k}"] = jaccard_at_k(retrieved_chunk_ids, ground_truth_chunk_ids, k)
    return row


def build_comparison(
    vector_summary: ModeRunSummary | None,
    hybrid_summary: ModeRunSummary | None,
    top_k_list: list[int],
) -> ComparisonSummary:
    """Build a side-by-side comparison of overall metrics at shared k cutoffs.

    Explicit `hybrid_available` branch when hybrid did not run or was
    unavailable; never fabricates hybrid rows (FR-019, SC-007).
    """

    hybrid_available = bool(hybrid_summary is not None and hybrid_summary.hybrid_available)
    keys = metric_keys_for(top_k_list)
    rows: list[dict[str, Any]] = []
    for key in keys:
        row: dict[str, Any] = {"metric": key}
        row["vector_only"] = (vector_summary.overall.get(key) if vector_summary else None)
        row["hybrid"] = (hybrid_summary.overall.get(key) if hybrid_available and hybrid_summary else None)
        rows.append(row)

    return ComparisonSummary(
        shared_top_k=list(top_k_list),
        vector_only=vector_summary,
        hybrid=hybrid_summary,
        hybrid_available=hybrid_available,
        rows=rows,
    )


def _case_result_to_dict(case: RetrievalCaseResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "qa_id": case.qa_id,
        "mode": case.mode,
        "question": case.question,
        "category": case.category,
        "difficulty": case.difficulty,
        "answer_type": case.answer_type,
        "ground_truth_chunk_ids": case.ground_truth_chunk_ids,
        "retrieved_chunk_ids": case.retrieved_chunk_ids,
        "error": case.error,
        **case.metrics,
    }
    if case.hybrid_diagnostics is not None:
        diag = case.hybrid_diagnostics
        payload["hybrid_diagnostics"] = {
            "traversal_mode": diag.traversal_mode,
            "traversal_start_ids": list(diag.traversal_start_ids),
            "traversal_visited_count": diag.traversal_visited_count,
            "whitelist_id_strs": list(diag.whitelist_id_strs),
            "whitelist_empty": diag.whitelist_empty,
            "filtered_vector_seed_chunk_ids": list(diag.filtered_vector_seed_chunk_ids),
            "expansion_seed_count": diag.expansion_seed_count,
            "expansion_added_count": diag.expansion_added_count,
            "expansion_empty_added": diag.expansion_empty_added,
            "extra_traversal_chunk_ids": list(diag.extra_traversal_chunk_ids),
            "overlays_available": diag.overlays_available,
            "prepass_empty_start": diag.prepass_empty_start,
            "hybrid_unavailable_reason": diag.hybrid_unavailable_reason,
        }
    return payload


def write_case_jsonl(path: Path, cases: list[RetrievalCaseResult]) -> None:
    """Persist per-case rows as JSONL. Never opens the read-only QA path."""

    write_jsonl(path, (_case_result_to_dict(case) for case in cases))


def write_metrics_json(path: Path, summary: ModeRunSummary, run_config: dict[str, Any]) -> None:
    """Persist aggregate metrics JSON, embedding the run config snapshot."""

    payload: dict[str, Any] = {
        "mode": summary.mode,
        "config": run_config,
        "counts": {
            "total_rows": summary.total_rows,
            "evaluated": summary.evaluated,
            "skipped_unanswerable": summary.skipped_unanswerable,
            "skipped_missing_ground_truth": summary.skipped_missing_ground_truth,
            "error_count": summary.error_count,
        },
        "overall": summary.overall,
        "by_category": summary.by_category,
        "by_difficulty": summary.by_difficulty,
        "by_answer_type": summary.by_answer_type,
        "hybrid_available": summary.hybrid_available,
        "hybrid_unavailable_reason": summary.hybrid_unavailable_reason,
    }
    write_json(path, payload)


def _group_table(groups: dict[str, Any], metric_keys: list[str]) -> list[str]:
    header = ["Group", "Count", *metric_keys]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---", "---:"] + ["---:"] * len(metric_keys)) + " |"]
    for group, values in groups.items():
        cells = [str(group), str(values.get("count", 0)), *[f"{values.get(key, 0.0):.4f}" for key in metric_keys]]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def write_markdown_report(
    path: Path,
    summary: ModeRunSummary,
    metric_keys: list[str],
    qa_path: str,
) -> None:
    """Write a self-contained markdown report readable without a kernel.

    Includes QA path, mode label, evaluated/skipped/error counts, and
    metric tables so a reviewer needs no notebook kernel (US4 AC2, SC-005).
    """

    lines = [
        f"# Retrieval Evaluation Report — {summary.mode}",
        "",
        f"- QA path: `{qa_path}`",
        f"- Mode: `{summary.mode}`",
        f"- Evaluated: {summary.evaluated}",
        f"- Skipped unanswerable: {summary.skipped_unanswerable}",
        f"- Skipped missing ground truth: {summary.skipped_missing_ground_truth}",
        f"- Errors: {summary.error_count}",
    ]
    if not summary.hybrid_available:
        lines.append(f"- Hybrid unavailable: `{summary.hybrid_unavailable_reason}`")
        lines.append("")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines.extend(["", "## Configuration", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(summary.config.items()))
    lines.extend(["", "## Overall", "", "| Metric | Value |", "| --- | ---: |"])
    lines.extend(f"| {key} | {summary.overall.get(key, 0.0):.4f} |" for key in metric_keys)
    lines.extend(["", "## By Category", ""])
    lines.extend(_group_table(summary.by_category, metric_keys))
    lines.extend(["", "## By Difficulty", ""])
    lines.extend(_group_table(summary.by_difficulty, metric_keys))
    lines.extend(["", "## By Answer Type", ""])
    lines.extend(_group_table(summary.by_answer_type, metric_keys))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_comparison_report(path: Path, comparison: ComparisonSummary) -> None:
    """Write the dual-mode comparison markdown report.

    When hybrid is unavailable, shows vector-only results with a clear
    unavailable note instead of inventing hybrid scores (FR-019, SC-007).
    """

    lines = ["# Vector-only vs Hybrid Comparison", ""]
    if not comparison.hybrid_available:
        reason = comparison.hybrid.hybrid_unavailable_reason if comparison.hybrid else "hybrid_not_run"
        lines.append(f"Hybrid comparison unavailable: `{reason}`")
        lines.append("")
        if comparison.vector_only is not None:
            lines.append("## Vector-only overall")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("| --- | ---: |")
            for key in metric_keys_for(comparison.shared_top_k):
                lines.append(f"| {key} | {comparison.vector_only.overall.get(key, 0.0):.4f} |")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines.extend(["| Metric | Vector-only | Hybrid |", "| --- | ---: | ---: |"])
    for row in comparison.rows:
        vector_value = row["vector_only"]
        hybrid_value = row["hybrid"]
        vector_cell = f"{vector_value:.4f}" if vector_value is not None else "n/a"
        hybrid_cell = f"{hybrid_value:.4f}" if hybrid_value is not None else "n/a"
        lines.append(f"| {row['metric']} | {vector_cell} | {hybrid_cell} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
