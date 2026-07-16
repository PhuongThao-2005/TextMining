from __future__ import annotations

import json
from pathlib import Path

from evaluation.retrieval_eval_report import (
    ComparisonSummary,
    HybridDiagnostics,
    ModeRunSummary,
    RetrievalCaseResult,
    build_case_metrics_row,
    build_comparison,
    metric_keys_for,
    write_case_jsonl,
    write_comparison_report,
    write_markdown_report,
    write_metrics_json,
)


def _mode_run_summary(
    mode: str = "vector_only",
    overall: dict | None = None,
    hybrid_available: bool = True,
    hybrid_unavailable_reason: str | None = None,
) -> ModeRunSummary:
    return ModeRunSummary(
        mode=mode,  # type: ignore[arg-type]
        config={"top_k": [5]},
        total_rows=3,
        evaluated=3,
        skipped_unanswerable=0,
        skipped_missing_ground_truth=0,
        error_count=0,
        overall=overall or {"recall@5": 1.0, "hit@5": 1.0, "mrr@5": 1.0, "ndcg@5": 1.0, "jaccard@5": 1.0},
        by_category={"contract": {"count": 3, "recall@5": 1.0}},
        by_difficulty={"easy": {"count": 3, "recall@5": 1.0}},
        by_answer_type={"extractive": {"count": 3, "recall@5": 1.0}},
        hybrid_available=hybrid_available,
        hybrid_unavailable_reason=hybrid_unavailable_reason,
    )


def test_build_case_metrics_row_uses_metrics_module_for_each_k():
    retrieved = ["c1", "c2", "c3"]
    ground_truth = {"c2"}
    row = build_case_metrics_row(retrieved, ground_truth, [1, 3])

    assert row["recall@1"] == 0.0
    assert row["recall@3"] == 1.0
    assert row["hit@3"] == 1.0
    assert 0.0 <= row["mrr@3"] <= 1.0
    assert 0.0 <= row["ndcg@3"] <= 1.0
    assert 0.0 <= row["jaccard@3"] <= 1.0


def test_build_case_metrics_row_handles_k_greater_than_retrieved_length():
    retrieved = ["c1"]
    ground_truth = {"c1"}
    row = build_case_metrics_row(retrieved, ground_truth, [10])

    assert row["recall@10"] == 1.0
    assert row["hit@10"] == 1.0


def test_metric_keys_for_orders_by_k_then_metric_name():
    keys = metric_keys_for([1, 5])
    assert keys == [
        "recall@1", "hit@1", "mrr@1", "ndcg@1", "jaccard@1",
        "recall@5", "hit@5", "mrr@5", "ndcg@5", "jaccard@5",
    ]


def test_build_comparison_both_modes_present():
    vector_summary = _mode_run_summary(mode="vector_only")
    hybrid_summary = _mode_run_summary(mode="hybrid")

    comparison = build_comparison(vector_summary, hybrid_summary, [5])

    assert comparison.hybrid_available is True
    assert comparison.vector_only is vector_summary
    assert comparison.hybrid is hybrid_summary
    row = next(r for r in comparison.rows if r["metric"] == "recall@5")
    assert row["vector_only"] == 1.0
    assert row["hybrid"] == 1.0


def test_build_comparison_hybrid_unavailable_does_not_fabricate_hybrid_rows():
    vector_summary = _mode_run_summary(mode="vector_only")
    hybrid_summary = _mode_run_summary(
        mode="hybrid", hybrid_available=False, hybrid_unavailable_reason="graph_missing"
    )

    comparison = build_comparison(vector_summary, hybrid_summary, [5])

    assert comparison.hybrid_available is False
    row = next(r for r in comparison.rows if r["metric"] == "recall@5")
    assert row["vector_only"] == 1.0
    assert row["hybrid"] is None


def test_build_comparison_hybrid_summary_none():
    vector_summary = _mode_run_summary(mode="vector_only")

    comparison = build_comparison(vector_summary, None, [5])

    assert comparison.hybrid_available is False
    assert comparison.hybrid is None
    row = next(r for r in comparison.rows if r["metric"] == "recall@5")
    assert row["hybrid"] is None


def test_write_case_jsonl_writes_one_row_per_case(tmp_path: Path):
    cases = [
        RetrievalCaseResult(
            qa_id="qa-1",
            mode="vector_only",
            question="What is X?",
            category="contract",
            difficulty="easy",
            answer_type="extractive",
            ground_truth_chunk_ids=["c1"],
            retrieved_chunk_ids=["c1", "c2"],
            metrics={"recall@5": 1.0},
        ),
        RetrievalCaseResult(
            qa_id="qa-2",
            mode="hybrid",
            question="What is Y?",
            category="contract",
            difficulty="hard",
            answer_type="extractive",
            ground_truth_chunk_ids=["c3"],
            retrieved_chunk_ids=["c4"],
            metrics={"recall@5": 0.0},
            hybrid_diagnostics=HybridDiagnostics(
                traversal_mode="structure",
                traversal_start_ids=("d1",),
                traversal_visited_count=2,
                whitelist_id_strs=("c3", "c4"),
                whitelist_empty=False,
                filtered_vector_seed_chunk_ids=("c4",),
                expansion_seed_count=1,
                expansion_added_count=0,
                expansion_empty_added=True,
                extra_traversal_chunk_ids=(),
                overlays_available=True,
                prepass_empty_start=False,
            ),
            error="timeout",
        ),
    ]

    path = tmp_path / "cases.jsonl"
    write_case_jsonl(path, cases)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    row1 = json.loads(lines[0])
    row2 = json.loads(lines[1])
    assert row1["qa_id"] == "qa-1"
    assert row1["recall@5"] == 1.0
    assert row2["qa_id"] == "qa-2"
    assert row2["error"] == "timeout"
    assert row2["hybrid_diagnostics"]["traversal_mode"] == "structure"
    assert row2["hybrid_diagnostics"]["traversal_start_ids"] == ["d1"]


def test_write_metrics_json_embeds_config_and_counts(tmp_path: Path):
    summary = _mode_run_summary(mode="vector_only")
    path = tmp_path / "metrics.json"

    write_metrics_json(path, summary, {"top_k": [5], "sample_limit": 10})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mode"] == "vector_only"
    assert payload["config"] == {"top_k": [5], "sample_limit": 10}
    assert payload["counts"]["evaluated"] == 3
    assert payload["overall"]["recall@5"] == 1.0
    assert payload["hybrid_available"] is True


def test_write_markdown_report_hybrid_available(tmp_path: Path):
    summary = _mode_run_summary(mode="vector_only")
    path = tmp_path / "report.md"

    write_markdown_report(path, summary, metric_keys_for([5]), qa_path="data/qa_final.jsonl")

    content = path.read_text(encoding="utf-8")
    assert "data/qa_final.jsonl" in content
    assert "## Overall" in content
    assert "## By Category" in content
    assert "recall@5" in content


def test_write_markdown_report_hybrid_unavailable_short_circuits(tmp_path: Path):
    summary = _mode_run_summary(
        mode="hybrid", hybrid_available=False, hybrid_unavailable_reason="graph_missing"
    )
    path = tmp_path / "report.md"

    write_markdown_report(path, summary, metric_keys_for([5]), qa_path="data/qa_final.jsonl")

    content = path.read_text(encoding="utf-8")
    assert "graph_missing" in content
    assert "## Overall" not in content


def test_write_comparison_report_both_modes(tmp_path: Path):
    vector_summary = _mode_run_summary(mode="vector_only")
    hybrid_summary = _mode_run_summary(mode="hybrid")
    comparison = build_comparison(vector_summary, hybrid_summary, [5])
    path = tmp_path / "comparison.md"

    write_comparison_report(path, comparison)

    content = path.read_text(encoding="utf-8")
    assert "Vector-only" in content
    assert "Hybrid" in content
    assert "recall@5" in content


def test_write_comparison_report_hybrid_unavailable_does_not_fabricate(tmp_path: Path):
    vector_summary = _mode_run_summary(mode="vector_only")
    hybrid_summary = _mode_run_summary(
        mode="hybrid", hybrid_available=False, hybrid_unavailable_reason="graph_missing"
    )
    comparison = build_comparison(vector_summary, hybrid_summary, [5])
    path = tmp_path / "comparison.md"

    write_comparison_report(path, comparison)

    content = path.read_text(encoding="utf-8")
    assert "graph_missing" in content
    assert "| Metric | Vector-only | Hybrid |" not in content
