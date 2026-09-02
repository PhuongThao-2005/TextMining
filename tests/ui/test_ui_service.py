from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pytest

from agent.simple_planner import SimplePlanner
from agent.tools import RetrievalTool
from retrieval.schema import RetrievalResult
from service.qa_service import (
    QAResources,
    TOP_K_MAX,
    TOP_K_MIN,
    QuestionRequest,
    UIConfigError,
    answer_question,
    apply_safe_overrides,
    format_safe_error,
    list_interactive_configs,
    load_ui_config_registry,
    normalize_context_rows,
    normalize_latency_rows,
    normalize_trace_rows,
    run_preflight,
)


@dataclass(frozen=True)
class _Chunk:
    chunk_id: str = "c1"
    chunk_text: str = "<script>alert('x')</script> Grounded legal context"
    citation_anchor: str = "Article 1"
    citation_label: str = "Document citation"
    title: str = "Fixture law"
    article_number: str = "1"
    unit_type: str = "article"
    path: str = "Chapter I / Article 1"
    validity_group: str = "current"
    legal_authority_rank: int = 1
    vector_score: float = 0.8
    rerank_score: float = 0.9
    id_str: str = "doc-1"
    parent_unit_id: str = "provision-1"


class _Retriever:
    def __init__(self, *, empty: bool = False, failure: Exception | None = None, delay: float = 0.0) -> None:
        self.empty = empty
        self.failure = failure
        self.delay = delay
        self.calls = 0

    def retrieve(self, question: str, *, filter_profile: str, top_n: int) -> RetrievalResult:
        del question, filter_profile, top_n
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.failure:
            raise self.failure
        chunks = [] if self.empty else [_Chunk()]
        return RetrievalResult(chunks=chunks, total_candidates=len(chunks), filter_profile_used="broad")


def _generator(row: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
    assert context and chunks
    if row["question"] == "generation fails":
        raise RuntimeError("api_key=fixture-secret generation failed")
    if row["question"] == "reasoning":
        return "<think>private reasoning</think>Final grounded answer [1]"
    return "Grounded answer [1]"


def _base_config(tmp_path: Path, *, backend: str = "hashing") -> dict[str, Any]:
    benchmark = tmp_path / "qa.jsonl"
    corpus = tmp_path / "corpus.jsonl"
    benchmark.write_text("{}\n", encoding="utf-8")
    corpus.write_text("{}\n", encoding="utf-8")
    dense: dict[str, Any] = {"enabled": True, "backend": backend, "model": "fixture-model"}
    if backend == "faiss":
        dense.update({"index_path": "index", "index_version": "fixture-v1"})
    return {
        "benchmark": {"path": str(benchmark), "version": "fixture-v1"},
        "corpus": {"path": str(corpus), "version": "fixture-v1"},
        "retrieval": {
            "top_k": 5, "filter_profile": "broad", "dense": dense,
            "sparse": {"enabled": False}, "graph": {"enabled": False},
            "fusion": {"enabled": False}, "reranker": {"enabled": False},
        },
        "generation": {
            "provider": "reference", "model": "reference", "prompt_strategy": "base",
            "temperature": 0.0, "top_p": 1.0, "max_output_tokens": 100,
            "timeout_seconds": 5.0, "max_retries": 0,
        },
        "judge": {"provider": "none"},
        "agent": {"enabled": False, "mode": "none", "implementation_status": "implemented"},
        "output": {"root": str(tmp_path / "runs")}, "seed": 42,
    }


def test_safe_error_summarizes_html_provider_response() -> None:
    error = format_safe_error("<!DOCTYPE html><html><head></head><body>not json</body></html>")

    assert "HTML page" in error
    assert "LLM_BASE_URL" in error
    assert "<html>" not in error.lower()


def _planner_config(tmp_path: Path) -> dict[str, Any]:
    config = _base_config(tmp_path)
    config["agent"] = {
        "enabled": True, "mode": "simple_planner", "implementation_status": "implemented",
        "max_steps": 3, "max_tool_calls": 1, "max_retries": 0,
        "deadline_seconds": 5.0, "allowed_tools": ["retrieve"], "trace_enabled": True,
    }
    return config


def _resources(retriever: _Retriever, generator=_generator, executor=None) -> QAResources:
    return QAResources(retriever, generator, None, ("fixture-secret",), executor)


def test_real_config_listing_is_deterministic_and_marks_multitool_deferred() -> None:
    registry = load_ui_config_registry()
    options = list_interactive_configs(registry, environ={})
    names = [option.name for option in options]
    assert names == sorted(names)
    assert "Example-Reference-Hashing" not in names
    assert {"LLM-BaseReasoning", "LLM-CoTReasoning", "LLM-LargerModel", "Agent-None-PlainRAG", "Agent-SimplePlanner"} <= set(names)
    multi = next(option for option in options if option.name == "Agent-MultiTool-Orchestrated")
    assert multi.status == "deferred" and not multi.runnable


def test_preflight_runnable_fixture_and_paths_are_safe(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["generation"]["api_key"] = "fixture-secret"
    result = run_preflight(config, config_name="fixture", project_root=tmp_path, environ={})
    assert result.runnable and result.status == "runtime-ready"
    diagnostics = json.dumps({"checks": [vars(check) for check in result.checks], "config": result.resolved_config})
    assert "fixture-secret" not in diagnostics
    assert result.resolved_config["generation"]["max_output_tokens"] == 100


def test_preflight_missing_model_api_key_and_base_url(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["generation"].update({
        "provider": "openai_compatible", "model": "env:UI_TEST_MODEL",
        "api_key_env": "UI_TEST_KEY", "base_url_env": "UI_TEST_URL",
    })
    result = run_preflight(config, config_name="fixture", project_root=tmp_path, environ={}, package_available=lambda name: True)
    text = " ".join(result.blockers)
    assert not result.runnable
    assert "UI_TEST_MODEL" in text and "UI_TEST_KEY" in text and "UI_TEST_URL" in text


def test_preflight_missing_faiss_artifacts_and_dependency(tmp_path: Path) -> None:
    config = _base_config(tmp_path, backend="faiss")
    index = tmp_path / "index"
    index.mkdir()
    result = run_preflight(config, config_name="fixture", project_root=tmp_path, package_available=lambda name: False)
    text = " ".join(result.blockers)
    assert "index.faiss" in text and "payloads.jsonl" in text
    assert "faiss-cpu" in text and "sentence-transformers" in text


def test_preflight_deferred_and_graph_rrf_stack_states(tmp_path: Path) -> None:
    deferred = _base_config(tmp_path)
    deferred["agent"] = {"enabled": False, "mode": "multi_tool", "implementation_status": "deferred", "reason": "needs tools"}
    result = run_preflight(deferred, config_name="multi", project_root=tmp_path)
    assert result.status == "deferred" and "needs tools" in result.blockers

    for component in ("graph", "reranker"):
        config = _base_config(tmp_path)
        config["retrieval"][component]["enabled"] = True
        blocked = run_preflight(config, config_name=component, project_root=tmp_path)
        assert not blocked.runnable
        assert any("dense, graph, fusion, and reranker together" in value for value in blocked.blockers)

    graph_path = tmp_path / "knowledge_graph.gpickle"
    graph_path.write_bytes(b"fixture")
    config = _base_config(tmp_path)
    config["retrieval"].update({
        "graph": {
            "enabled": True, "backend": "structural_pickle", "path": str(graph_path),
            "max_hop": 2, "max_context": 30,
        },
        "fusion": {"enabled": True, "strategy": "rrf", "rrf_k": 60},
        "reranker": {
            "enabled": True, "backend": "cross_encoder", "scope": "global",
            "model": "fixture-cross-encoder", "candidate_limit": 30,
        },
    })
    ready = run_preflight(
        config,
        config_name="graph-rrf",
        project_root=tmp_path,
        package_available=lambda name: True,
    )
    assert ready.runnable
    assert {check.name for check in ready.checks if check.status == "ready"} >= {"graph", "fusion", "reranker"}

    offline = run_preflight(
        config,
        config_name="graph-rrf",
        project_root=tmp_path,
        environ={"HF_HUB_OFFLINE": "1"},
        package_available=lambda name: True,
    )
    assert not offline.runnable
    assert any("HF_HUB_OFFLINE=1" in blocker for blocker in offline.blockers)


def test_overrides_are_bounded_deterministic_and_non_mutating(tmp_path: Path) -> None:
    source = _base_config(tmp_path)
    original = deepcopy(source)
    request = QuestionRequest("q", "fixture", top_k_override=12, filter_profile="historical", graph_enabled_override=False)
    first = apply_safe_overrides(source, request)
    second = apply_safe_overrides(source, request)
    assert first == second and first["retrieval"]["top_k"] == 12
    assert first["retrieval"]["filter_profile"] == "historical"
    assert source == original

    for invalid in (TOP_K_MIN - 1, TOP_K_MAX + 1):
        with pytest.raises(UIConfigError, match="top-k"):
            apply_safe_overrides(source, QuestionRequest("q", "fixture", top_k_override=invalid))


def test_generation_overrides_are_bounded_and_non_mutating(tmp_path: Path) -> None:
    source = _base_config(tmp_path)
    original = deepcopy(source)
    effective = apply_safe_overrides(
        source,
        QuestionRequest(
            "q", "fixture",
            generation_model_override="env:LLM_LARGER_MODEL",
            prompt_strategy_override="reasoning",
            temperature_override=0.4,
            top_p_override=0.8,
            max_output_tokens_override=2048,
            timeout_seconds_override=90.0,
            max_retries_override=3,
        ),
    )
    generation = effective["generation"]
    assert generation["model"] == "env:LLM_LARGER_MODEL"
    assert generation["prompt_strategy"] == "reasoning"
    assert generation["temperature"] == 0.4
    assert generation["top_p"] == 0.8
    assert generation["max_output_tokens"] == 2048
    assert generation["timeout_seconds"] == 90.0
    assert generation["max_retries"] == 3
    assert source == original

    with pytest.raises(UIConfigError, match="Prompt strategy"):
        apply_safe_overrides(source, QuestionRequest("q", "fixture", prompt_strategy_override="unsupported"))
    with pytest.raises(UIConfigError, match="temperature"):
        apply_safe_overrides(source, QuestionRequest("q", "fixture", temperature_override=2.5))


def test_graph_and_reranker_enable_the_complete_stack(tmp_path: Path) -> None:
    config = _base_config(tmp_path, backend="faiss")
    with pytest.raises(UIConfigError, match="enabled together"):
        apply_safe_overrides(config, QuestionRequest("q", "fixture", graph_enabled_override=True))
    with pytest.raises(UIConfigError, match="enabled together"):
        apply_safe_overrides(config, QuestionRequest("q", "fixture", reranker_enabled_override=True))
    effective = apply_safe_overrides(
        config,
        QuestionRequest("q", "fixture", graph_enabled_override=True, reranker_enabled_override=True),
    )
    retrieval = effective["retrieval"]
    assert retrieval["graph"]["enabled"] is True
    assert retrieval["fusion"]["enabled"] is True
    assert retrieval["reranker"]["enabled"] is True
    assert retrieval["graph"]["path"] == "data/graph/knowledge_graph.gpickle"


def test_plain_service_success_preserves_context_rank_score_latency_and_strips_reasoning(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    response = answer_question(
        QuestionRequest("reasoning", "fixture"), registry={"fixture": config},
        resources=_resources(_Retriever()), project_root=tmp_path,
    )
    assert response.status == "completed" and response.answer == "Final grounded answer [1]"
    assert "private reasoning" not in json.dumps(as_serializable(response))
    context = response.contexts[0]
    assert (context.rank, context.score, context.vector_score, context.rerank_score) == (1, 0.9, 0.8, 0.9)
    assert context.citation == "Article 1" and response.latency["dense_retrieval"] is not None
    assert response.diagnostics["prompt_template_hash"]
    assert [source.citation_id for source in response.citation_sources] == [1]
    assert response.citation_references[0].marker == "[1]"
    assert response.citation_metrics["citation_validity_rate"] == 1.0
    assert response.suggested_followups


def test_service_exposes_authoritative_invalid_citation_warning(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    response = answer_question(
        QuestionRequest("invalid citation", "fixture"), registry={"fixture": config},
        resources=_resources(_Retriever(), generator=lambda *_: "Claim with invalid source [99]."),
        project_root=tmp_path,
    )
    assert response.status == "completed"
    assert "[99]" not in (response.answer or "")
    assert response.citation_sources == ()
    assert "99" in response.citation_warnings[0]
    assert response.diagnostics["citation_contract"]["invalid_ids"] == [99]


def test_simple_planner_service_preserves_trace(tmp_path: Path) -> None:
    config = _planner_config(tmp_path)
    retriever = _Retriever()
    response = answer_question(
        QuestionRequest("normal", "planner"), registry={"planner": config},
        resources=_resources(retriever), project_root=tmp_path,
    )
    assert response.status == "completed" and retriever.calls == 1
    assert [row["event"] for row in response.trace] == ["planner_decision", "tool_call", "generation"]
    assert response.latency["agent_total"] is not None


def test_empty_input_and_empty_retrieval_abstain_without_generation(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    empty_input = answer_question(QuestionRequest("  ", "fixture"), registry={"fixture": config}, project_root=tmp_path)
    assert empty_input.status == "failed" and empty_input.error and empty_input.error.stage == "validation"

    called = False
    def generator(row: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
        nonlocal called
        called = True
        return "must not be used"
    response = answer_question(
        QuestionRequest("q", "fixture"), registry={"fixture": config},
        resources=_resources(_Retriever(empty=True), generator), project_root=tmp_path,
    )
    assert response.status == "abstained" and response.abstained and response.answer is None
    assert not called


def test_fixed_insufficient_evidence_answer_is_an_abstention(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    response = answer_question(
        QuestionRequest("insufficient", "fixture"), registry={"fixture": config},
        resources=_resources(
            _Retriever(), generator=lambda *_: "Không có đủ thông tin trong ngữ cảnh được cung cấp."
        ),
        project_root=tmp_path,
    )
    assert response.status == "abstained"
    assert response.abstained is True
    assert response.answer is None
    assert response.citation_sources == ()


def test_retrieval_and_generation_failures_are_sanitized(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    retrieval = answer_question(
        QuestionRequest("q", "fixture"), registry={"fixture": config},
        resources=_resources(_Retriever(failure=RuntimeError("token=fixture-secret"))), project_root=tmp_path,
    )
    assert retrieval.status == "failed" and retrieval.error and retrieval.error.stage == "retrieval"
    assert "fixture-secret" not in json.dumps(as_serializable(retrieval))

    generation = answer_question(
        QuestionRequest("generation fails", "fixture"), registry={"fixture": config},
        resources=_resources(_Retriever()), project_root=tmp_path,
    )
    assert generation.status == "failed" and generation.error and generation.error.stage == "generation"
    assert "fixture-secret" not in json.dumps(as_serializable(generation))


def test_agent_step_limit_and_deadline_fail_safely(tmp_path: Path) -> None:
    config = _planner_config(tmp_path)
    retriever = _Retriever()
    limited = SimplePlanner(
        retrieval_tool=RetrievalTool(retriever), generator=_generator, top_k=5,
        filter_profile="broad", max_steps=2, max_tool_calls=1, max_retries=0, deadline_seconds=5,
    )
    response = answer_question(
        QuestionRequest("q", "planner"), registry={"planner": config},
        resources=_resources(retriever, executor=limited.execute), project_root=tmp_path,
    )
    assert response.status == "failed" and response.error and "StepLimitExceeded" in response.error.message

    slow = _Retriever(delay=0.01)
    deadline = SimplePlanner(
        retrieval_tool=RetrievalTool(slow), generator=_generator, top_k=5,
        filter_profile="broad", max_steps=3, max_tool_calls=1, max_retries=0, deadline_seconds=0.001,
    )
    response = answer_question(
        QuestionRequest("q", "planner"), registry={"planner": config},
        resources=_resources(slow, executor=deadline.execute), project_root=tmp_path,
    )
    assert response.status == "failed" and response.error and "AgentDeadlineExceeded" in response.error.message


def test_normalizers_preserve_nulls_order_truncation_and_plain_text() -> None:
    long_text = "<b>unsafe</b>" + "x" * 400
    contexts = normalize_context_rows([{"rank": 2, "chunk_id": "c", "text": long_text, "score": None}])
    assert contexts[0].score is None and len(contexts[0].preview) == 300
    assert contexts[0].text.startswith("<b>unsafe</b>")
    latency = normalize_latency_rows({"total": 5.0})
    assert next(row for row in latency if row["stage"] == "generation")["latency_ms"] is None
    assert next(row for row in latency if row["stage"] == "agent_total")["latency_ms"] is None
    trace = normalize_trace_rows([{"step": 2, "event": "tool_call", "document": "do not keep"}, {"step": 1, "event": "decision"}])
    assert [row["step"] for row in trace] == [1, 2] and "document" not in trace[1]


def as_serializable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: as_serializable(item) for key, item in vars(value).items()}
    if isinstance(value, (list, tuple)):
        return [as_serializable(item) for item in value]
    if isinstance(value, dict):
        return {key: as_serializable(item) for key, item in value.items()}
    return value
