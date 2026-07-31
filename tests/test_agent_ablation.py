from __future__ import annotations

import csv
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pytest

from agent.contracts import AgentAction, AgentStatus, PlannerDecision, ToolRequest
from agent.simple_planner import SimplePlanner
from agent.tools import RetrievalTool
from evaluation.e2e_runner import aggregate_agent_metrics, records_from_rows, run_e2e_evaluation
from retrieval.schema import RetrievalResult
from scripts.aggregate_ablation_results import aggregate_ablation_results
from scripts.run_ablation_config import (
    AGENT_ABLATION_CONFIG_NAMES,
    AblationConfigError,
    load_ablation_configs,
    run_ablation_config,
    validate_ablation_config,
    validate_agent_ablation_fairness,
)


@dataclass(frozen=True)
class _Chunk:
    chunk_id: str = "c1"
    chunk_text: str = "Grounded legal context"
    citation_anchor: str = "Article 1"
    citation_label: str = ""
    parent_unit_id: str = "p1"
    id_str: str = "d1"
    rerank_score: float = 1.0


class _Retriever:
    def __init__(self, *, empty: bool = False, failure: Exception | None = None) -> None:
        self.empty = empty
        self.failure = failure
        self.calls = 0

    def retrieve(self, question: str, *, filter_profile: str, top_n: int) -> RetrievalResult:
        del question, filter_profile, top_n
        self.calls += 1
        if self.failure:
            raise self.failure
        chunks = [] if self.empty else [_Chunk()]
        return RetrievalResult(chunks=chunks, total_candidates=len(chunks), filter_profile_used="broad")


def _generator(row: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
    assert context and chunks
    if row.get("question") == "generation failure":
        raise RuntimeError("api_key=generator-secret unavailable")
    return "grounded answer"


def _planner(retriever: _Retriever, **overrides: Any) -> SimplePlanner:
    values = {
        "retrieval_tool": RetrievalTool(retriever, sensitive_values=["retriever-secret"]),
        "generator": _generator,
        "top_k": 5,
        "filter_profile": "broad",
        "max_steps": 3,
        "max_tool_calls": 1,
        "max_retries": 0,
        "deadline_seconds": 10.0,
    }
    values.update(overrides)
    return SimplePlanner(**values)


def _base_config(benchmark: Path, corpus: Path, output: Path) -> dict[str, Any]:
    return {
        "benchmark": {"path": str(benchmark), "version": "fixture-v1"},
        "corpus": {"path": str(corpus), "version": "fixture-v1"},
        "retrieval": {
            "top_k": 5, "filter_profile": "broad",
            "dense": {"enabled": True, "backend": "hashing", "index_version": "fixture-index-v1"},
            "sparse": {"enabled": False}, "graph": {"enabled": False},
            "fusion": {"enabled": False}, "reranker": {"enabled": False},
        },
        "generation": {
            "provider": "reference", "model": "reference", "prompt_strategy": "base",
            "temperature": 0.0, "top_p": 1.0, "max_output_tokens": 128,
            "timeout_seconds": 10.0, "max_retries": 0,
        },
        "judge": {"provider": "none"}, "output": {"root": str(output)}, "seed": 42,
        "metadata": {"purpose": "offline agent fixture", "experiment_family": "agent-orchestration"},
    }


def _config_file(tmp_path: Path) -> tuple[Path, Path]:
    benchmark, corpus, output = tmp_path / "qa.jsonl", tmp_path / "corpus.jsonl", tmp_path / "runs"
    rows = [
        {"qa_id": "ok", "question": "normal question", "reference_answer": "grounded answer", "ground_truth": {"chunk_ids": ["c1"]}},
        {"qa_id": "bad", "question": "generation failure", "reference_answer": "answer"},
    ]
    benchmark.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    corpus.write_text("{}\n", encoding="utf-8")
    base = _base_config(benchmark, corpus, output)
    plain = deepcopy(base)
    plain["agent"] = {"enabled": False, "mode": "none", "implementation_status": "implemented"}
    planner = deepcopy(base)
    planner["agent"] = {
        "enabled": True, "mode": "simple_planner", "implementation_status": "implemented",
        "max_steps": 3, "max_tool_calls": 1, "max_retries": 0, "deadline_seconds": 10.0,
        "allowed_tools": ["retrieve"], "trace_enabled": True,
    }
    multi = deepcopy(base)
    multi["agent"] = {"enabled": False, "mode": "multi_tool", "implementation_status": "deferred"}
    path = tmp_path / "configs.json"
    path.write_text(json.dumps({"schema_version": 1, "configs": {
        "Agent-None-PlainRAG": plain, "Agent-SimplePlanner": planner,
        "Agent-MultiTool-Orchestrated": multi,
    }}), encoding="utf-8")
    return path, output


def test_named_configs_and_fairness_contract() -> None:
    configs = load_ablation_configs()
    assert all(name in configs for name in AGENT_ABLATION_CONFIG_NAMES)
    assert configs["Agent-None-PlainRAG"]["agent"]["mode"] == "none"
    planner = configs["Agent-SimplePlanner"]["agent"]
    assert planner["allowed_tools"] == ["retrieve"]
    assert 1 <= planner["max_steps"] <= 3 and planner["max_tool_calls"] == 1
    assert configs["Agent-MultiTool-Orchestrated"]["agent"]["implementation_status"] == "deferred"
    validate_agent_ablation_fairness(configs)


@pytest.mark.parametrize("path,value", [
    (("retrieval", "top_k"), 9), (("generation", "model"), "other"),
    (("generation", "temperature"), 0.5), (("benchmark", "version"), "other"),
])
def test_fairness_rejects_unintended_changes(path: tuple[str, str], value: object) -> None:
    configs = load_ablation_configs()
    changed = deepcopy(configs)
    changed["Agent-SimplePlanner"][path[0]][path[1]] = value
    with pytest.raises(AblationConfigError, match="Unfair agent ablation"):
        validate_agent_ablation_fairness(changed)


def test_unknown_mode_is_rejected() -> None:
    config = deepcopy(load_ablation_configs()["Agent-None-PlainRAG"])
    config["agent"] = {"enabled": True, "mode": "autonomous"}
    with pytest.raises(AblationConfigError, match="Unknown agent mode"):
        validate_ablation_config(config, config_name="bad")


def test_retrieval_tool_success_empty_failure_validation_and_redaction() -> None:
    success = RetrievalTool(_Retriever()).execute(ToolRequest("question", 5))
    assert success.status == "completed" and success.result_count == 1 and success.latency_ms is not None
    assert RetrievalTool(_Retriever(empty=True)).execute(ToolRequest("question", 5)).status == "empty"
    failed = RetrievalTool(
        _Retriever(failure=RuntimeError("token=retriever-secret")), sensitive_values=["retriever-secret"]
    ).execute(ToolRequest("question", 5))
    assert failed.status == "failed" and "retriever-secret" not in (failed.error_message or "")
    invalid = RetrievalTool(_Retriever()).execute(ToolRequest(" ", 0))
    assert invalid.error_type == "ValidationError"


def test_planner_success_abstention_empty_failure_and_trace_bounds() -> None:
    retriever = _Retriever()
    success = _planner(retriever).execute({"question": "  normal   question "})
    assert success.status is AgentStatus.COMPLETED and retriever.calls == 1
    assert [event.event for event in success.trace] == ["planner_decision", "tool_call", "generation"]
    assert len(success.trace_dicts()) <= 3 and "reasoning" not in json.dumps(success.trace_dicts()).lower()
    assert _planner(_Retriever()).execute({"question": " "}).status is AgentStatus.ABSTAINED
    empty = _planner(_Retriever(empty=True)).execute({"question": "question"})
    assert empty.status is AgentStatus.ABSTAINED and empty.reason_code == "empty_context"
    failed = _planner(_Retriever(failure=TimeoutError("secret=retriever-secret"))).execute({"question": "q"})
    assert failed.status is AgentStatus.FAILED and "retriever-secret" not in (failed.error_message or "")


def test_planner_rejects_unapproved_action_and_enforces_limits() -> None:
    fake_decision = lambda question: PlannerDecision("web_search", str(question), "bad")  # type: ignore[arg-type]
    result = _planner(_Retriever(), decision_policy=fake_decision).execute({"question": "q"})
    assert result.status is AgentStatus.FAILED and result.error_type == "UnapprovedAction"
    limited = _planner(_Retriever(), max_steps=2).execute({"question": "q"})
    assert limited.reason_code == "step_limit_reached" and limited.tool_call_count == 0


def test_e2e_planner_isolates_failures_preserves_trace_context_and_metrics() -> None:
    retriever = _Retriever()
    rows = [
        {"qa_id": "ok", "question": "q", "reference_answer": "grounded answer", "ground_truth": {"chunk_ids": ["c1"]}},
        {"qa_id": "bad", "question": "generation failure", "reference_answer": "answer"},
        {"qa_id": "empty", "question": " ", "reference_answer": "answer"},
    ]
    result = run_e2e_evaluation(
        records_from_rows(rows), retriever=retriever, generator=_generator, retrieval_top_k=5,
        filter_profile="broad", case_executor=_planner(retriever).execute,
        sensitive_values=["generator-secret"],
    )
    assert [row["status"] for row in result.predictions] == ["success", "failed", "skipped"]
    assert result.predictions[0]["retrieved_context"] and result.predictions[0]["agent_trace"]
    assert result.predictions[0]["latency_ms"]["planner_decision"] is not None
    assert "generator-secret" not in json.dumps(result.predictions + result.errors)
    assert result.metrics["agent_metrics"]["retrieval_invocation_rate"] == pytest.approx(2 / 3)


def test_agent_metric_denominators_and_plain_null_tool_success() -> None:
    metrics = aggregate_agent_metrics([
        {"tool_call_count": 1, "successful_tool_calls": 1, "retrieval_invoked": True, "agent_status": "completed"},
        {"tool_call_count": 1, "successful_tool_calls": 0, "retrieval_invoked": True, "agent_status": "failed"},
        {"tool_call_count": 0, "successful_tool_calls": 0, "retrieval_invoked": False, "agent_status": "abstained"},
    ])
    assert metrics["denominators"] == {"cases": 3, "attempted_tool_calls": 2}
    assert metrics["tool_call_success_rate"] == 0.5
    assert metrics["average_tool_calls_per_case"] == pytest.approx(2 / 3)
    plain = aggregate_agent_metrics([{"retrieval_invoked": True, "agent_status": "completed"}])
    assert plain["tool_call_success_rate"] is None


def test_runner_manifests_aggregate_agent_variants_and_defer_multitool(tmp_path: Path) -> None:
    config_file, output = _config_file(tmp_path)
    for name, run_id in (("Agent-None-PlainRAG", "plain"), ("Agent-SimplePlanner", "planner")):
        outcome = run_ablation_config(
            name, config_file=config_file, output_root=output, run_id=run_id,
            retriever=_Retriever(), generator=_generator, project_root=tmp_path,
        )
        assert outcome.status == ("completed" if name.endswith("PlainRAG") else "completed")
        manifest_text = (outcome.output_dir / "manifest.json").read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        assert manifest["agent_version"] and manifest["trace_schema_version"]
        assert "generator-secret" not in manifest_text
    deferred = run_ablation_config(
        "Agent-MultiTool-Orchestrated", config_file=config_file, output_root=output,
        run_id="multi", retriever=_Retriever(), generator=_generator, project_root=tmp_path,
    )
    assert deferred.status == "deferred" and "second approved" in (deferred.error or "")

    aggregate = aggregate_ablation_results(output)
    with aggregate.output_csv.open(encoding="utf-8", newline="") as handle:
        rows = {row["run_id"]: row for row in csv.DictReader(handle)}
    assert rows["plain"]["agent_mode"] == "none"
    assert rows["planner"]["agent_mode"] == "simple_planner"
    assert rows["multi"]["status"] == "deferred"
    assert rows["plain"]["average_planner_latency_ms"] == ""
    report = aggregate.output_report.read_text(encoding="utf-8")
    assert "## Agent Comparison" in report
    assert "reports observed values only and does not select a best agent" in report


def test_structural_dry_runs_do_not_create_artifacts(tmp_path: Path) -> None:
    config_file, output = _config_file(tmp_path)
    statuses = {
        name: run_ablation_config(name, config_file=config_file, output_root=output, dry_run=True).status
        for name in AGENT_ABLATION_CONFIG_NAMES
    }
    assert statuses == {
        "Agent-None-PlainRAG": "completed", "Agent-SimplePlanner": "completed",
        "Agent-MultiTool-Orchestrated": "deferred",
    }
    assert not output.exists()
