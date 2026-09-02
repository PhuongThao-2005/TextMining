from __future__ import annotations

import json
from pathlib import Path
import zipfile

import nbformat
import pandas as pd
import pytest

from evaluation.ablation_analysis import (
    RECOMMENDATION_BOUNDARY,
    AblationAnalysisError,
    add_baseline_deltas,
    build_family_table,
    classify_ablation_family,
    classify_summary,
    compute_pareto_frontier,
    diagnostic_rows,
    export_analysis_outputs,
    generate_mechanical_observations,
    load_ablation_summary,
    select_comparable_rows,
    summarize_coverage,
)


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "notebooks" / "ablation_report.ipynb"


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "run_id": "run-a",
        "config_name": "LLM-BaseReasoning",
        "status": "completed",
        "eligible_for_comparison": "true",
        "exclusion_reason": "",
        "benchmark_name": "official",
        "benchmark_version": "v1",
        "corpus_name": "legal",
        "corpus_version": "v2",
        "evaluation_schema_version": "1",
        "index_version": "idx-1",
        "graph_version": "",
        "token_f1": "0.7",
        "rouge_l": "0.6",
        "context_recall_at_k": "0.8",
        "average_total_latency_ms": "100",
        "median_total_latency_ms": "90",
        "generation_latency_ms": "70",
        "successful_cases": "10",
        "failed_cases": "0",
        "notes": "fixture only",
    }
    row.update(overrides)
    return row


def _write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _classified(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["eligible_for_comparison"] = frame["eligible_for_comparison"].map({"true": True, "false": False}).astype("boolean")
    for column in ("token_f1", "rouge_l", "context_recall_at_k", "average_total_latency_ms", "median_total_latency_ms", "generation_latency_ms", "successful_cases", "failed_cases"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Float64")
    return classify_summary(frame)


def test_notebook_is_valid_clean_python_notebook() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    assert notebook.metadata.kernelspec.name == "python3"
    assert all(cell.get("execution_count") is None for cell in notebook.cells if cell.cell_type == "code")
    assert all(not cell.get("outputs") for cell in notebook.cells if cell.cell_type == "code")


def test_notebook_is_clone_first_safe_and_defaults_to_no_aggregation() -> None:
    raw = NOTEBOOK.read_text(encoding="utf-8")
    notebook = json.loads(raw)
    sources = ["".join(cell.get("source", [])) for cell in notebook["cells"]]
    joined = "\n".join(sources)
    assert 'REPO_URL = "https://github.com/PhuongThao-2005/TextMining.git"' in joined
    assert "RUN_AGGREGATOR = False" in joined
    assert "subprocess.run([" in joined
    clone_index = next(index for index, source in enumerate(sources) if '"clone"' in source)
    project_import_index = next(index for index, source in enumerate(sources) if "from evaluation.ablation_analysis import" in source)
    assert clone_index < project_import_index
    assert "C:\\" not in raw and "C:/Users/" not in raw
    assert "ghp_" not in raw and "sk-" not in raw and "API_KEY =" not in raw


def test_load_valid_csv_and_preserve_optional_absence(tmp_path: Path) -> None:
    loaded = load_ablation_summary(_write_csv(tmp_path / "summary.csv", [_row()]))
    assert loaded.validation.is_valid
    assert loaded.validation.eligible_row_count == 1
    assert "agent_failure_rate" not in loaded.frame


def test_load_missing_and_malformed_csv(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_ablation_summary(tmp_path / "missing.csv")
    malformed = tmp_path / "bad.csv"
    malformed.write_text('run_id,config_name\n"unterminated', encoding="utf-8")
    with pytest.raises(AblationAnalysisError):
        load_ablation_summary(malformed)


def test_load_reports_missing_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "summary.csv"
    pd.DataFrame([{"run_id": "x"}]).to_csv(path, index=False)
    loaded = load_ablation_summary(path)
    assert not loaded.validation.is_valid
    assert "config_name" in loaded.validation.missing_required_columns


def test_load_detects_duplicates_and_multiple_groups(tmp_path: Path) -> None:
    rows = [_row(), _row(), _row(benchmark_version="v2", config_name="LLM-StrongReasoning")]
    loaded = load_ablation_summary(_write_csv(tmp_path / "summary.csv", rows))
    assert loaded.validation.duplicate_run_ids == ("run-a",)
    assert loaded.validation.duplicate_row_count == 1
    assert loaded.validation.compatibility_group_count == 2


def test_load_preserves_null_and_flags_invalid_numeric_and_boolean(tmp_path: Path) -> None:
    rows = [_row(token_f1=None), _row(run_id="run-b", eligible_for_comparison="maybe", token_f1="bad")]
    loaded = load_ablation_summary(_write_csv(tmp_path / "summary.csv", rows))
    assert pd.isna(loaded.frame.loc[0, "token_f1"])
    assert pd.isna(loaded.frame.loc[1, "token_f1"])
    assert loaded.validation.invalid_numeric_cells == ("token_f1@3",)
    assert loaded.validation.invalid_boolean_rows == (3,)


@pytest.mark.parametrize(
    ("name", "family"),
    [
        ("Retrieval-DenseOnly", "retrieval"),
        ("Embed-ChunkOnly-Dense", "embedding"),
        ("Rerank-RRF-Hybrid", "reranker"),
        ("Retrieval-Dense-Graph", "graph"),
        ("LLM-BaseReasoning", "llm"),
        ("Agent-SimplePlanner", "agent"),
        ("Mystery", "unclassified"),
    ],
)
def test_family_classification(name: str, family: str) -> None:
    assert classify_ablation_family({"config_name": name}) == family


def test_explicit_family_metadata_precedes_name_fallback() -> None:
    assert classify_ablation_family({"config_name": "LLM-BaseReasoning", "ablation_family": "retrieval"}) == "retrieval"
    assert classify_ablation_family({"config_name": "LLM-BaseReasoning"}, {"experiment": {"family": "graph"}}) == "graph"


def test_eligibility_selection_preserves_excluded_failed_deferred_and_invalid() -> None:
    frame = _classified([
        _row(),
        _row(run_id="excluded", config_name="LLM-StrongReasoning", eligible_for_comparison="false", exclusion_reason="benchmark mismatch"),
        _row(run_id="deferred", config_name="Agent-MultiTool", status="deferred", eligible_for_comparison="false"),
        _row(run_id="failed", config_name="Agent-SimplePlanner", status="failed", eligible_for_comparison="false"),
        _row(run_id="invalid", config_name="Mystery", benchmark_name=None),
    ])
    comparable = select_comparable_rows(frame)
    excluded, failed = diagnostic_rows(frame)
    assert comparable["run_id"].tolist() == ["run-a"]
    assert set(excluded["run_id"]) == {"excluded", "deferred", "failed", "invalid"}
    assert set(failed["run_id"]) == {"deferred", "failed"}
    assert "invalid" not in set(comparable["run_id"])


def test_no_eligible_runs_reported(tmp_path: Path) -> None:
    loaded = load_ablation_summary(_write_csv(tmp_path / "summary.csv", [_row(eligible_for_comparison="false")]))
    assert loaded.validation.eligible_row_count == 0
    assert any("No eligible" in message for message in loaded.validation.messages())


def test_coverage_has_stable_family_rows_and_missing_expected_configs() -> None:
    frame = _classified([_row(), _row(run_id="agent", config_name="Agent-MultiTool", status="deferred", eligible_for_comparison="false")])
    coverage = summarize_coverage(frame, {"llm": ["LLM-BaseReasoning", "LLM-StrongReasoning"]})
    assert list(coverage.columns) == ["scope", "measure", "value"]
    missing = coverage.loc[(coverage.scope == "llm") & (coverage.measure == "missing_expected_configs"), "value"].iloc[0]
    assert missing == "LLM-StrongReasoning"
    assert coverage.loc[(coverage.scope == "agent") & (coverage.measure == "eligible_completed_rows"), "value"].iloc[0] == 0


def test_family_tables_are_stable_keep_nulls_and_can_include_ineligible() -> None:
    frame = _classified([_row(run_id="z", token_f1=None), _row(run_id="a", config_name="LLM-AlternativeReasoning", eligible_for_comparison="false")])
    eligible = build_family_table(frame, "llm")
    all_rows = build_family_table(frame, "llm", include_ineligible=True)
    assert eligible["config_name"].tolist() == ["LLM-BaseReasoning"]
    assert all_rows["config_name"].tolist() == ["LLM-AlternativeReasoning", "LLM-BaseReasoning"]
    assert pd.isna(eligible.loc[0, "token_f1"])
    assert list(eligible.columns)[0:3] == ["config_name", "generation_model", "prompt_strategy"]


def test_multiple_family_tables_have_documented_schema_when_empty() -> None:
    frame = _classified([_row()])
    assert not build_family_table(frame, "llm").empty
    retrieval = build_family_table(frame, "retrieval")
    assert retrieval.empty and "recall_at_1" in retrieval.columns


def test_baseline_deltas_are_absolute_preserve_nulls_and_never_guess() -> None:
    table = pd.DataFrame([
        {"config_name": "LLM-BaseReasoning", "token_f1": 0.7, "rouge_l": 0.6},
        {"config_name": "LLM-StrongReasoning", "token_f1": 0.8, "rouge_l": pd.NA},
    ])
    result = add_baseline_deltas(table, "llm")
    assert result.loc[1, "delta_token_f1_absolute"] == pytest.approx(0.1)
    assert pd.isna(result.loc[1, "delta_rouge_l_absolute"])
    guessed = add_baseline_deltas(table.iloc[1:].copy(), "retrieval")
    assert not any(column.startswith("delta_") for column in guessed)


def test_pareto_one_candidate_and_dominated_run() -> None:
    frame = _classified([_row(), _row(run_id="b", config_name="LLM-StrongReasoning", token_f1="0.6", average_total_latency_ms="120")])
    pareto = compute_pareto_frontier(frame, "token_f1", "average_total_latency_ms")
    assert pareto["run_id"].tolist() == ["run-a"]


def test_pareto_multiple_candidates_ties_and_deterministic_order() -> None:
    rows = [
        _row(run_id="b", config_name="LLM-StrongReasoning", token_f1="0.8", average_total_latency_ms="120"),
        _row(run_id="a", token_f1="0.7", average_total_latency_ms="90"),
        _row(run_id="c", config_name="LLM-AlternativeReasoning", token_f1="0.8", average_total_latency_ms="120"),
    ]
    frame = _classified(rows)
    first = compute_pareto_frontier(frame, "token_f1", "average_total_latency_ms")
    second = compute_pareto_frontier(frame.sample(frac=1, random_state=3), "token_f1", "average_total_latency_ms")
    assert first["config_name"].tolist() == ["LLM-AlternativeReasoning", "LLM-StrongReasoning", "LLM-BaseReasoning"]
    assert first["config_name"].tolist() == second["config_name"].tolist()


def test_pareto_ignores_missing_ineligible_and_incompatible_rows() -> None:
    frame = _classified([
        _row(),
        _row(run_id="missing", config_name="LLM-StrongReasoning", token_f1=None),
        _row(run_id="excluded", config_name="LLM-AlternativeReasoning", token_f1="1", average_total_latency_ms="1", eligible_for_comparison="false"),
        _row(run_id="incompatible", config_name="Agent-SimplePlanner", token_f1="1", average_total_latency_ms="1", benchmark_name=None),
    ])
    assert compute_pareto_frontier(frame, "token_f1", "average_total_latency_ms")["run_id"].tolist() == ["run-a"]


def test_observations_are_mechanical_include_counts_missing_families_and_boundary() -> None:
    frame = _classified([_row()])
    observations = generate_mechanical_observations(frame, "token_f1", "average_total_latency_ms")
    text = "\n".join(observations)
    assert "Highest available token_f1: LLM-BaseReasoning (0.7)" in text
    assert "Lowest available average_total_latency_ms: LLM-BaseReasoning (100 ms)" in text
    assert "successful cases range 10-10" in text
    assert "Families without an eligible completed run" in text
    assert RECOMMENDATION_BOUNDARY in text


def test_observations_handle_no_data_without_a_final_choice() -> None:
    frame = _classified([_row(status="deferred", eligible_for_comparison="false")])
    text = "\n".join(generate_mechanical_observations(frame, "token_f1", "average_total_latency_ms"))
    assert "No eligible completed runs" in text
    assert "final main-pipeline recommendation cannot be finalized" in text
    assert "best pipeline is" not in text.lower()


def test_export_writes_schema_markdown_manifest_plots_and_zip_without_sensitive_files(tmp_path: Path) -> None:
    frame = _classified([_row(), _row(run_id="b", config_name="LLM-StrongReasoning", token_f1="0.8", average_total_latency_ms="130")])
    source = tmp_path / "ablation_summary.csv"
    _write_csv(source, [_row()])
    destination = export_analysis_outputs(frame, tmp_path / "outputs", source, "abc123", create_zip=True)
    required = {
        "coverage_summary.csv", "retrieval_ablation_table.csv", "embedding_ablation_table.csv",
        "reranker_ablation_table.csv", "graph_ablation_table.csv", "llm_ablation_table.csv",
        "agent_ablation_table.csv", "pareto_candidates.csv", "excluded_runs.csv",
        "failed_deferred_runs.csv", "mechanical_observations.md", "analysis_manifest.json",
        "quality_vs_average_latency.png", "quality_vs_median_latency.png",
        "llm_quality_vs_generation_latency.png",
    }
    assert required.issubset({path.name for path in destination.iterdir()})
    assert destination.with_suffix(".zip").is_file()
    manifest = json.loads((destination / "analysis_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_csv"].endswith("ablation_summary.csv")
    assert "abc123" == manifest["repository_commit"]
    with zipfile.ZipFile(destination.with_suffix(".zip")) as bundle:
        names = bundle.namelist()
    assert all("benchmark" not in name and "index" not in name and "secret" not in name for name in names)


def test_export_is_collision_safe_and_plots_only_with_sufficient_data(tmp_path: Path) -> None:
    frame = _classified([_row()])
    first = export_analysis_outputs(frame, tmp_path / "outputs", "token=hidden/ablation_summary.csv", "abc", create_zip=False)
    second = export_analysis_outputs(frame, tmp_path / "outputs", "token=hidden/ablation_summary.csv", "abc", create_zip=False)
    assert first != second and first.is_dir() and second.is_dir()
    assert not list(first.glob("*.png"))
    manifest_text = (first / "analysis_manifest.json").read_text(encoding="utf-8")
    assert "hidden" not in manifest_text
