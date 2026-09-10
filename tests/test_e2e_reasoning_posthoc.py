from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ablation_work" / "e2e_LLM_Reasoning" / "analyze_posthoc.py"
SPEC = importlib.util.spec_from_file_location("e2e_reasoning_posthoc", SCRIPT)
assert SPEC and SPEC.loader
POSTHOC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POSTHOC)


def test_bootstrap_is_deterministic_and_bounded() -> None:
    values = [-0.2, -0.1, 0.0, 0.1, 0.2]
    first = POSTHOC.bootstrap_mean_ci(values, reps=200, seed=7)
    second = POSTHOC.bootstrap_mean_ci(values, reps=200, seed=7)
    assert first == second
    assert first[0] is not None and first[1] is not None
    assert first[0] <= 0.0 <= first[1]


def test_saved_gpt_pair_matches_posthoc_plan() -> None:
    root = ROOT / "ablation_work" / "e2e_LLM_Reasoning"
    runs = POSTHOC.load_runs(root)
    pairs = POSTHOC.choose_pairs(runs)
    base, cot = next(pair for pair in pairs if pair[0]["model"] == "gpt-4o-mini")
    summary, case_rows, _ = POSTHOC.paired_analysis(base, cot, reps=50, seed=42)

    assert summary["fully_paired"] is True
    assert summary["shared_successful_answerable_n"] == 400
    token_f1 = summary["metrics"]["token_f1"]
    assert (token_f1["wins"], token_f1["ties"], token_f1["losses"]) == (79, 164, 157)

    strata, mismatches = POSTHOC.evidence_analysis(case_rows, reps=20, seed=42)
    assert [record["n"] for record in strata] == [138, 29, 233]
    assert mismatches == 0


def test_saved_decision_and_citation_metrics_match_plan() -> None:
    root = ROOT / "ablation_work" / "e2e_LLM_Reasoning"
    runs = POSTHOC.load_runs(root)
    base = runs["4o-mini-base"]
    cot = runs["4o-mini-CoT"]

    base_decision = POSTHOC.answerability_analysis(base)
    cot_decision = POSTHOC.answerability_analysis(cot)
    assert base_decision["scheduled_metrics"]["unanswerable_recognition_rate"] == 0.98
    assert cot_decision["scheduled_metrics"]["unanswerable_recognition_rate"] == 0.98
    assert base_decision["scheduled_metrics"]["false_refusal_rate"] == 0.2125
    assert cot_decision["scheduled_metrics"]["false_refusal_rate"] == 0.195

    base_citation = POSTHOC.citation_analysis(base)
    cot_citation = POSTHOC.citation_analysis(cot)
    assert base_citation["citation_presence_rate"] == 0.7825
    assert cot_citation["citation_presence_rate"] == 0.81
    assert base_citation["invalid_marker_count"] == 0
    assert cot_citation["invalid_marker_count"] == 0
