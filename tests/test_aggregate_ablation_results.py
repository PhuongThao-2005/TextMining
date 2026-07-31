from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.aggregate_ablation_results import (
    AggregationError,
    CSV_COLUMNS,
    aggregate_ablation_results,
    discover_run_directories,
    main,
)


def _manifest(
    run_id: str,
    *,
    config_name: str = "baseline",
    status: str = "completed",
    benchmark_version: str = "bench-v1",
    corpus_version: str = "corpus-v1",
    config_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "config_name": config_name,
        "resolved_config": {
            "benchmark": {"path": "fixtures/qa.jsonl", "version": benchmark_version},
            "corpus": {"path": "fixtures/corpus.jsonl", "version": corpus_version},
        },
        "config_file_path": "configs/ablation_configs.yaml",
        "config_hash": config_hash or f"hash-{run_id}",
        "start_time": "2026-07-28T00:00:00+00:00",
        "end_time": "2026-07-28T00:01:00+00:00" if status != "running" else None,
        "status": status,
        "benchmark_path": "fixtures/qa.jsonl",
        "benchmark_version": benchmark_version,
        "corpus_path": "fixtures/corpus.jsonl",
        "corpus_version": corpus_version,
        "index_path": "fixtures/index",
        "index_version": "index-v1",
        "graph_path": None,
        "graph_version": None,
        "git_commit": "abc123",
        "output_directory": run_id,
        "output_artifacts": {},
        "completed_case_count": 2 if status == "completed" else 0,
        "failed_case_count": 0,
        "skipped_case_count": 0,
        "evaluated_case_count": 2 if status == "completed" else 0,
        "error_summary": None if status == "completed" else f"{status} fixture",
    }


def _write_run(
    root: Path,
    run_id: str,
    *,
    manifest: dict[str, Any] | None = None,
    e2e: dict[str, Any] | str | None = None,
    latency: dict[str, Any] | str | None = None,
    retrieval: dict[str, Any] | None = None,
) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    payload = manifest or _manifest(run_id)
    (run_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (run_dir / "resolved_config.yaml").write_text(
        "benchmark:\n  version: fixture\ncorpus:\n  version: fixture\n", encoding="utf-8"
    )
    if payload.get("status") == "completed":
        e2e = e2e if e2e is not None else {
            "counts": {"total_input": 2, "successful": 2, "failed": 0, "skipped": 0, "evaluated": 2},
            "overall": {
                "exact_match": 0.5,
                "token_f1": 0.75,
                "rouge_l": 0.7,
                "unanswerable_accuracy": 1.0,
                "context_recall@k": 0.8,
            },
        }
        latency = latency if latency is not None else {
            "unit": "milliseconds",
            "stages": {
                "dense_retrieval": {"mean": 10.0, "median": 9.0, "p95": 14.0},
                "total": {"mean": 100.0, "median": 90.0, "p95": 140.0},
            },
        }
        (run_dir / "e2e_metrics.json").write_text(
            e2e if isinstance(e2e, str) else json.dumps(e2e), encoding="utf-8"
        )
        (run_dir / "latency.json").write_text(
            latency if isinstance(latency, str) else json.dumps(latency), encoding="utf-8"
        )
        (run_dir / "e2e_predictions.jsonl").write_text(
            json.dumps({"qa_id": "qa-1", "status": "success"}) + "\n", encoding="utf-8"
        )
        (run_dir / "errors.jsonl").write_text("", encoding="utf-8")
        (run_dir / "report.md").write_text("# Fixture report\n", encoding="utf-8")
    if retrieval is not None:
        (run_dir / "retrieval_metrics.json").write_text(json.dumps(retrieval), encoding="utf-8")
    return run_dir


def _rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_discovery_empty_missing_recursive_and_ignores_outputs(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "ablation_summary.csv").write_text("not,a,run\n", encoding="utf-8")
    (runs / "ablation_report.md").write_text("# report\n", encoding="utf-8")
    (runs / "batch_summary.json").write_text("{}", encoding="utf-8")
    assert discover_run_directories(runs) == []
    result = aggregate_ablation_results(runs)
    assert result.discovered_count == 0
    assert result.output_csv.is_file()
    assert result.output_report.is_file()

    _write_run(runs / "nested", "b-run")
    _write_run(runs, "a-run")
    _write_run(runs / ".cache", "cached-run")
    _write_run(runs / "temp", "temporary-run")
    assert [path.name for path in discover_run_directories(runs)] == ["a-run", "b-run"]
    with pytest.raises(AggregationError, match="does not exist"):
        discover_run_directories(tmp_path / "missing")


def test_compatible_runs_load_all_metrics_and_are_deterministic(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_run(
        runs,
        "run-b",
        retrieval={
            "overall": {
                "recall@1": 0.1,
                "recall@5": 0.5,
                "recall@10": 0.9,
                "mrr@10": 0.4,
                "ndcg@10": 0.6,
            }
        },
    )
    _write_run(runs, "run-a")

    first = aggregate_ablation_results(runs)
    csv_first = first.output_csv.read_text(encoding="utf-8")
    report_first = first.output_report.read_text(encoding="utf-8")
    second = aggregate_ablation_results(runs)

    assert csv_first == second.output_csv.read_text(encoding="utf-8")
    assert report_first == second.output_report.read_text(encoding="utf-8")
    rows = _rows(first.output_csv)
    assert list(rows[0]) == CSV_COLUMNS
    assert [row["run_id"] for row in rows] == ["run-a", "run-b"]
    assert all(row["eligible_for_comparison"] == "true" for row in rows)
    assert rows[1]["token_f1"] == "0.75"
    assert rows[1]["recall_at_10"] == "0.9"
    assert rows[1]["mrr"] == "0.4"
    assert rows[1]["average_total_latency_ms"] == "100.0"
    assert "Pareto candidates" in report_first


def test_optional_metrics_remain_blank_and_zero_is_preserved(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    e2e = {
        "counts": {"total_input": 1, "successful": 1, "failed": 0, "skipped": 0, "evaluated": 1},
        "overall": {"exact_match": 0.0, "token_f1": None},
    }
    latency = {"stages": {"total": {"mean": 0.0, "median": None}}}
    _write_run(runs, "partial-metrics", e2e=e2e, latency=latency)

    result = aggregate_ablation_results(runs)
    row = _rows(result.output_csv)[0]
    assert row["exact_match"] == "0.0"
    assert row["token_f1"] == ""
    assert row["median_total_latency_ms"] == ""
    assert row["sparse_retrieval_latency_ms"] == ""
    assert "Unavailable optional E2E fields" in row["notes"]
    assert "N/A" in result.output_report.read_text(encoding="utf-8")


def test_completed_missing_or_malformed_mandatory_artifact_is_invalid(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    missing = _write_run(runs, "missing")
    (missing / "latency.json").unlink()
    _write_run(runs, "malformed", e2e="{broken")

    result = aggregate_ablation_results(runs)
    rows = {row["run_id"]: row for row in _rows(result.output_csv)}
    assert result.invalid_count == 2
    assert rows["missing"]["eligible_for_comparison"] == "false"
    assert "artifact is missing" in rows["missing"]["notes"]
    assert "Malformed E2E metrics" in rows["malformed"]["notes"]


def test_malformed_manifest_missing_fields_invalid_status_and_directory_mismatch(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    malformed = runs / "bad-json"
    malformed.mkdir()
    (malformed / "manifest.json").write_text("{bad", encoding="utf-8")
    _write_run(runs, "missing-fields", manifest={"run_id": "missing-fields", "status": "completed"})
    invalid = _manifest("invalid-status", status="surprising")
    _write_run(runs, "invalid-status", manifest=invalid)
    mismatch = _manifest("claimed-id", status="failed")
    _write_run(runs, "directory-id", manifest=mismatch)

    result = aggregate_ablation_results(runs)
    assert result.invalid_count == 4
    report = result.output_report.read_text(encoding="utf-8")
    assert "Malformed manifest.json" in report
    assert "Missing required manifest field" in report
    assert "Invalid status" in report
    assert "does not match manifest run_id" in report


def test_duplicate_run_id_config_collision_and_name_version_reuse_are_reported(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    one = _manifest("one", config_hash="same-hash")
    two = _manifest("two", config_hash="same-hash")
    _write_run(runs, "one", manifest=one)
    _write_run(runs, "two", manifest=two)
    duplicate = _manifest("one", status="failed")
    _write_run(runs / "nested", "one", manifest=duplicate)
    other_version = _manifest("other-version", config_name="baseline", benchmark_version="bench-v2")
    _write_run(runs, "other-version", manifest=other_version)

    result = aggregate_ablation_results(runs)
    report = result.output_report.read_text(encoding="utf-8")
    assert "Duplicate run_id" in report
    assert "Config collision" in report
    assert "reused across incompatible" in report


def test_compatibility_primary_group_is_largest_and_tie_break_is_deterministic(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_run(runs, "v2-one", manifest=_manifest("v2-one", benchmark_version="v2"))
    _write_run(
        runs,
        "other-corpus",
        manifest=_manifest("other-corpus", corpus_version="corpus-v2"),
    )
    _write_run(runs, "v1-one", manifest=_manifest("v1-one"))
    _write_run(runs, "v1-two", manifest=_manifest("v1-two"))
    result = aggregate_ablation_results(runs)
    rows = {row["run_id"]: row for row in _rows(result.output_csv)}
    assert rows["v1-one"]["eligible_for_comparison"] == "true"
    assert rows["v1-two"]["eligible_for_comparison"] == "true"
    assert rows["v2-one"]["eligible_for_comparison"] == "false"
    assert rows["other-corpus"]["eligible_for_comparison"] == "false"
    assert "differs from the selected group" in rows["v2-one"]["exclusion_reason"]
    assert "differs from the selected group" in rows["other-corpus"]["exclusion_reason"]
    assert "v2-one" in result.output_report.read_text(encoding="utf-8")
    assert "other-corpus" in result.output_report.read_text(encoding="utf-8")

    tie_runs = tmp_path / "ties"
    tie_runs.mkdir()
    _write_run(tie_runs, "z", manifest=_manifest("z", benchmark_version="z-version"))
    _write_run(tie_runs, "a", manifest=_manifest("a", benchmark_version="a-version"))
    tie_result = aggregate_ablation_results(tie_runs)
    assert tie_result.selected_compatibility_group is not None
    assert tie_result.selected_compatibility_group[1] == "a-version"


@pytest.mark.parametrize("status", ["failed", "skipped", "deferred", "needs-rerun", "running"])
def test_non_completed_states_are_retained_without_metrics(tmp_path: Path, status: str) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_run(runs, f"run-{status}", manifest=_manifest(f"run-{status}", status=status))
    result = aggregate_ablation_results(runs)
    row = _rows(result.output_csv)[0]
    assert row["status"] == status
    assert row["eligible_for_comparison"] == "false"
    assert f"status is {status}" in row["exclusion_reason"]
    assert f"{status} fixture" in row["notes"]


def test_cli_exit_policy_success_with_bad_run_and_failure_for_missing_dir(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    bad = runs / "bad"
    bad.mkdir()
    (bad / "manifest.json").write_text("{", encoding="utf-8")
    assert main(["--runs-dir", str(runs)]) == 0
    assert main(["--runs-dir", str(tmp_path / "missing")]) == 2


def test_validation_error_status_is_invalid_and_outputs_cannot_replace_artifacts(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    run_dir = _write_run(
        runs,
        "validation-error",
        manifest=_manifest("validation-error", status="validation-error"),
    )
    result = aggregate_ablation_results(runs)
    assert result.invalid_count == 1
    assert _rows(result.output_csv)[0]["status"] == "validation-error"

    with pytest.raises(AggregationError, match="overwrite a discovered run artifact"):
        aggregate_ablation_results(runs, output_csv=run_dir / "manifest.json")
