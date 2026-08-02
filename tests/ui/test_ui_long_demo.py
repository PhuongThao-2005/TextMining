from types import SimpleNamespace

from generation.citations import CitationSource, validate_evidence_span
from service.qa_service import QuestionRequest
from service.ui_models import ConversationTurn, resolve_turn_citation
from service.ui_runtime import DemoAnswerProvider


LONG_QUESTION = "Show a complete example with several supporting sources"


def request(question: str) -> QuestionRequest:
    return QuestionRequest(question, "demo")


def test_long_demo_is_default_realistic_multi_source_scenario() -> None:
    response = DemoAnswerProvider().answer(request(LONG_QUESTION))
    assert response.diagnostics["demo_scenario"] == "long-answer-three-sources"
    assert response.is_mock and response.diagnostics["production_call_performed"] is False
    answer = response.answer or ""
    assert len(answer) > 900
    assert len(answer.split("\n\n")) >= 5
    assert "1. " in answer and "2. " in answer and "3. " in answer
    assert all(marker in answer for marker in ("[1]", "[2]", "[3]"))
    assert "[1][2]" in answer and "[2][3]" in answer
    assert len(response.citation_sources) == len(response.contexts) == 3
    assert all(source.is_mock and source.text for source in response.citation_sources)


def test_long_demo_explicit_spans_match_each_source_exactly() -> None:
    response = DemoAnswerProvider().answer(request(LONG_QUESTION))
    for source in response.citation_sources:
        evidence = source.evidence
        assert evidence and evidence.match_type == "explicit_offsets"
        assert evidence.start_char is not None and evidence.end_char is not None
        assert source.text[evidence.start_char:evidence.end_char] == evidence.quote
        assert validate_evidence_span(source.text, evidence, context_id=source.context_id).status == "valid"
    assert response.diagnostics["evidence_spans_available"] == 3
    assert response.diagnostics["evidence_spans_valid"] == 3
    assert response.diagnostics["evidence_spans_rejected"] == 0


def test_single_source_scenario_keeps_additional_source_deterministic() -> None:
    response = DemoAnswerProvider().answer(request("Show a single source example"))
    assert len(response.citation_sources) == 1
    assert len(response.contexts) == 2
    assert response.contexts[1].chunk_id == "demo-background-note-04"


def test_citation_resolution_is_turn_specific_and_rejects_invalid_ids() -> None:
    first_source = CitationSource(1, "turn-one", "doc-1", "chunk-1", "First", None, None, None,
                                  None, None, 7, None, "first text")
    second_source = CitationSource(1, "turn-two", "doc-2", "chunk-2", "Second", None, None, None,
                                   None, None, 2, None, "second text")
    turns = [
        ConversationTurn("one", SimpleNamespace(citation_sources=(first_source,)), 41),
        ConversationTurn("two", SimpleNamespace(citation_sources=(second_source,)), 42),
    ]
    assert resolve_turn_citation(turns, 41, 1) is first_source
    assert resolve_turn_citation(turns, 42, 1) is second_source
    assert resolve_turn_citation(turns, 42, 99) is None
    assert first_source.rank == 7  # Citation ID is never assumed to equal retrieval rank.

