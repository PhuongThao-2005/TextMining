from dataclasses import replace
import json
from pathlib import Path

from service.qa_service import QuestionRequest, QuestionResponse
from service.ui_runtime import (
    AUTO_MODE, DEMO_MODE, PRODUCTION_MODE, DemoAnswerProvider,
    ProductionAnswerProvider, ProductionReadiness, load_demo_qa_examples, resolve_runtime_mode,
)


def request(question: str) -> QuestionRequest:
    return QuestionRequest(question, "fixture")


def readiness(ready: bool) -> ProductionReadiness:
    return ProductionReadiness(ready, "fixture", "faiss", "fixture-model", (), () if ready else ("missing",), (), (), None, {})


def test_demo_provider_is_deterministic_and_never_calls_production() -> None:
    called = False

    def production(_: QuestionRequest) -> QuestionResponse:
        nonlocal called
        called = True
        raise AssertionError("production must not run")

    provider = DemoAnswerProvider()
    first = provider.answer(request("What information is required for a request?"))
    second = provider.answer(request("What information is required for a request?"))
    assert first == second
    assert first.mode == "demo" and first.is_mock and not called
    assert len(first.citation_sources) == 1
    assert all(source.is_mock for source in first.citation_sources)
    assert any(row.is_mock for row in first.contexts)
    assert first.diagnostics["production_call_performed"] is False


def test_demo_scenarios_cover_multiple_abstention_invalid_and_trace() -> None:
    provider = DemoAnswerProvider()
    multiple = provider.answer(request("Show an example with multiple sources."))
    assert [source.citation_id for source in multiple.citation_sources] == [1, 2]
    assert multiple.trace and len(multiple.contexts) == 3
    abstained = provider.answer(request("Show an abstention example."))
    assert abstained.status == "abstained" and abstained.answer is None
    invalid = provider.answer(request("Show an invalid citation preview."))
    assert "[99]" not in (invalid.answer or "")
    assert invalid.citation_sources == () and "99" in invalid.citation_warnings[0]


def test_mode_selection_never_silently_falls_back_from_production() -> None:
    assert resolve_runtime_mode(DEMO_MODE, readiness(True)).active_mode == "demo"
    blocked = resolve_runtime_mode(PRODUCTION_MODE, readiness(False))
    assert blocked.active_mode == "production" and not blocked.production_ready
    assert "demo" in (blocked.banner or "").lower()
    assert resolve_runtime_mode(AUTO_MODE, readiness(True)).active_mode == "production"
    fallback = resolve_runtime_mode(AUTO_MODE, readiness(False))
    assert fallback.active_mode == "demo" and "demo data" in (fallback.banner or "").lower()


def test_production_provider_returns_same_schema_and_marks_production() -> None:
    demo = DemoAnswerProvider().answer(request("one citation"))
    base = replace(demo, is_mock=False, mode="production", citation_sources=(), contexts=())
    provider = ProductionAnswerProvider(lambda _: base)
    result = provider.answer(request("real question"))
    assert isinstance(result, QuestionResponse)
    assert result.mode == "production" and result.is_mock is False
    assert result.question == "real question"


def test_production_provider_rejects_mock_marked_objects() -> None:
    demo = DemoAnswerProvider().answer(request("one citation"))
    provider = ProductionAnswerProvider(lambda _: demo)
    try:
        provider.answer(request("real question"))
    except RuntimeError as exc:
        assert "mock-marked" in str(exc)
    else:
        raise AssertionError("mock data crossed the production provider boundary")


def test_production_followup_calls_the_production_answerer_again() -> None:
    calls: list[str] = []
    demo = DemoAnswerProvider().answer(request("one citation"))
    base = replace(demo, is_mock=False, mode="production", citation_sources=(), contexts=())
    provider = ProductionAnswerProvider(lambda item: calls.append(item.question) or base)
    provider.answer(request("first"))
    provider.answer(request("follow-up"))
    assert calls == ["first", "follow-up"]


def test_demo_followups_are_deterministic_and_turn_citations_restart() -> None:
    provider = DemoAnswerProvider()
    first = provider.answer(request("one citation"))
    second = provider.answer(request("Show an example with multiple sources."))
    assert first.citation_sources[0].citation_id == 1
    assert second.citation_sources[0].citation_id == 1
    assert first.suggested_followups == provider.answer(request("one citation")).suggested_followups


def test_demo_provider_can_render_qa_final_jsonl_without_api(tmp_path: Path) -> None:
    qa_path = tmp_path / "qa_final.jsonl"
    row = {
        "qa_id": "qa-demo-1",
        "question": "Người lao động được nghỉ phép năm bao nhiêu ngày?",
        "reference_answer": "Người lao động làm đủ 12 tháng được nghỉ hằng năm 12 ngày.",
        "answer_explanation": "Câu trả lời được lấy từ quy định về nghỉ hằng năm.",
        "answer_type": "extractive",
        "ground_truth": {
            "document_ids": ["doc-1"],
            "provision_ids": ["doc-1::article::113"],
            "chunk_ids": ["doc-1::article::113::chunk::1"],
        },
        "category": "single_hop",
        "difficulty": "easy",
        "corpus_version": "fixture",
        "as_of_date": "2026-08-24",
    }
    qa_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    provider = DemoAnswerProvider(project_root=tmp_path, qa_path=qa_path)

    response = provider.answer(request(row["question"]))

    assert response.mode == "demo" and response.is_mock
    assert response.diagnostics["production_call_performed"] is False
    assert response.diagnostics["demo_scenario"] == "qa-final:qa-demo-1"
    assert response.answer and "12 ngày" in response.answer
    assert response.citation_sources and response.citation_sources[0].is_mock
    assert response.contexts and response.contexts[0].chunk_id == "doc-1::article::113::chunk::1"


def test_demo_qa_examples_use_answerable_rows(tmp_path: Path) -> None:
    qa_path = tmp_path / "qa_final.jsonl"
    rows = [
        {"question": "Không trả lời được?", "answer_type": "unanswerable"},
        {"question": "Câu hỏi answerable?", "answer_type": "extractive"},
    ]
    qa_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

    assert load_demo_qa_examples(tmp_path, qa_path=qa_path) == (("Quy định", "Câu hỏi answerable?"),)
