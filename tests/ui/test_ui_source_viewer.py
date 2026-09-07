from types import SimpleNamespace

import pytest

from generation.citations import CitationSource, EvidenceSpan
from service.qa_service import ContextRow
from service.ui_models import (
    ConversationTurn, SourceSelection, build_source_actions, build_source_cards,
    citation_control_key, clear_source_selection, parse_source_selection,
    resolve_turn_citation, select_source_for_turn,
)
from src.ui.view_models import (
    build_source_text_segments, format_retrieved_text, resolve_source_text,
    source_segments_html,
)


def source(*, url: str | None = None, mock: bool = False, text: str = "Full retrieved chunk") -> CitationSource:
    return CitationSource(
        1, "chunk-ctx", "document-1", "chunk-1", "Source title", "Section 2",
        "Article 4", 7, "documents/source.pdf", url, 9, 0.812, text, mock,
    )


def test_view_source_is_internal_and_external_url_is_separate() -> None:
    actions = build_source_actions(source(url="https://example.test/document"))
    assert actions.view_label == "View source"
    assert actions.original_label == "Open original document ↗"
    assert actions.original_url == "https://example.test/document"
    assert actions.original_url not in actions.view_label


def test_demo_and_url_less_production_sources_remain_internal_only() -> None:
    demo = build_source_actions(source(url="https://example.test/demo", mock=True))
    production = build_source_actions(source())
    assert demo.view_label == production.view_label == "View source"
    assert demo.original_url is None and production.original_url is None


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "file:///tmp/source", "https://user:pass@example.test/a",
    "https://example.test/a?access_token=secret", "not-a-url",
])
def test_only_valid_external_urls_are_exposed(url: str) -> None:
    assert build_source_actions(source(url=url)).original_url is None


def test_selection_is_typed_turn_aware_and_has_stable_occurrence_keys() -> None:
    selection = SourceSelection(12, 1, False)
    assert parse_source_selection(selection.to_state()) == selection
    assert parse_source_selection({"turn_id": 0, "citation_id": 1}) is None
    assert parse_source_selection({"turn_id": 12, "citation_id": 0}) is None
    assert citation_control_key(12, 1, 3) == "citation-12-1-3"


def test_only_a_source_in_the_current_turn_can_be_selected() -> None:
    selected = select_source_for_turn((source(),), 12, 1, viewer_open=True)
    assert selected == SourceSelection(12, 1, True)
    assert select_source_for_turn((source(),), 12, 99, viewer_open=True) is None
    assert select_source_for_turn((source(),), 0, 1) is None


def test_close_or_conversation_reset_clears_only_source_selection() -> None:
    conversation = [ConversationTurn("question", SimpleNamespace(citation_sources=(source(),)), 12)]
    state = {"selected_source": SourceSelection(12, 1, True).to_state(), "conversation": conversation}
    clear_source_selection(state)
    assert state["selected_source"] is None
    assert state["conversation"] is conversation


def test_same_citation_id_resolves_only_inside_selected_turn() -> None:
    first = source(text="turn one")
    second = CitationSource(**{**source(text="turn two").__dict__, "context_id": "turn-two"})
    turns = (
        ConversationTurn("first", SimpleNamespace(citation_sources=(first,)), 5),
        ConversationTurn("second", SimpleNamespace(citation_sources=(second,)), 6),
    )
    assert resolve_turn_citation(turns, 5, 1) is first
    assert resolve_turn_citation(turns, 6, 1) is second
    assert resolve_turn_citation(turns, 6, 99) is None


def test_viewer_model_preserves_full_chunk_and_metadata() -> None:
    value = source(text="x" * 10_000)
    card = build_source_cards((value,))[0]
    assert card.full_text == "x" * 10_000
    assert card.document_id == "document-1" and card.chunk_id == "chunk-1"
    assert card.detail == "Article 4 · Section 2" and card.page == 7
    assert card.rank == 9 and card.score == 0.812


def test_viewer_resolves_full_chunk_from_normalized_response_without_refetching() -> None:
    bounded_source = source(text="bounded preview")
    full_chunk = "full context " + ("x" * 10_000)
    context = ContextRow(
        9, 0.812, None, None, "document-1", None, "chunk-1", "Source title",
        "Article 4", None, "documents/source.pdf", None, full_chunk, "preview",
    )
    assert resolve_source_text(bounded_source, (context,)) == full_chunk
    assert resolve_source_text(bounded_source, ()) == "bounded preview"


def test_missing_metadata_is_preserved_as_missing_not_invented() -> None:
    value = CitationSource(1, "ctx", None, None, None, None, None, None, None, None, 4, None, "text")
    card = build_source_cards((value,))[0]
    assert card.document_id is None and card.source_path is None and card.url is None
    assert card.title == "Retrieved source 1"


def test_safe_highlight_and_mapping_only_source_rendering() -> None:
    text = '<script>alert("x")</script> exact evidence'
    quote = "exact evidence"
    start = text.index(quote)
    exact = build_source_text_segments(
        text, EvidenceSpan("chunk-ctx", start, len(text), quote, "explicit_offsets"),
        context_id="chunk-ctx",
    )
    assert exact.status == "valid" and exact.label == "Exact recorded evidence"
    html = source_segments_html(exact)
    assert "<script>" not in html and "&lt;script&gt;" in html
    unavailable = build_source_text_segments(text, None, context_id="chunk-ctx")
    assert unavailable.status == "unavailable"
    assert not any(segment.highlighted for segment in unavailable.segments)


def test_exact_unique_quote_and_invalid_offsets_never_guess() -> None:
    text = "prefix exact quote suffix"
    exact_quote = build_source_text_segments(
        text, EvidenceSpan("chunk-ctx", quote="exact quote", match_type="exact_unique_quote"),
        context_id="chunk-ctx",
    )
    assert exact_quote.status == "valid" and exact_quote.label == "Exact quote match"
    assert [segment.text for segment in exact_quote.segments if segment.highlighted] == ["exact quote"]

    invalid = build_source_text_segments(
        text, EvidenceSpan("chunk-ctx", 0, 999, "wrong", "explicit_offsets"),
        context_id="chunk-ctx",
    )
    assert invalid.status == "invalid"
    assert not any(segment.highlighted for segment in invalid.segments)
    assert "".join(segment.text for segment in invalid.segments) == text


def test_retrieved_legal_text_is_formatted_for_source_viewing() -> None:
    text = (
        "Điều 111. Nghỉ hằng năm 1. Người lao động có đủ 12 tháng làm việc "
        "thì được nghỉ hằng năm như sau: a) 12 ngày làm việc đối với người "
        "làm công việc trong điều kiện bình thường; b) 14 ngày làm việc đối "
        "với người làm công việc nặng nhọc; c) 16 ngày làm việc đối với người "
        "làm công việc đặc biệt nặng nhọc. 2. Người sử dụng lao động có quyền "
        "quy định lịch nghỉ hằng năm."
    )
    formatted = format_retrieved_text(text)

    assert formatted.startswith("Điều 111. Nghỉ hằng năm\n1. Người lao động")
    assert "\na) 12 ngày" in formatted
    assert "\nb) 14 ngày" in formatted
    assert "\nc) 16 ngày" in formatted
    assert "\n2. Người sử dụng lao động" in formatted

    html = source_segments_html(build_source_text_segments(text, None, context_id="chunk-ctx"))
    assert "<br" not in html
    assert "\na) 12 ngày" in html


def test_retrieved_legal_text_splits_dash_numbered_clauses() -> None:
    text = (
        "Điều 74. 1- Người lao động có 12 tháng làm việc thì được nghỉ hằng năm, "
        "hưởng nguyên lương theo quy định sau đây: a) 12 ngày làm việc; "
        "b) 14 ngày làm việc; c) 16 ngày làm việc. 2- Thời gian đi đường "
        "ngoài ngày nghỉ hằng năm do Chính phủ quy định."
    )
    formatted = format_retrieved_text(text)

    assert formatted.startswith("Điều 74.\n1- Người lao động")
    assert "\na) 12 ngày" in formatted
    assert "\nb) 14 ngày" in formatted
    assert "\nc) 16 ngày" in formatted
    assert "\n2- Thời gian đi đường" in formatted
