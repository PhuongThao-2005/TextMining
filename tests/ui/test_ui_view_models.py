from generation.citations import CitationSource
from service.qa_service import ContextRow
from src.ui.view_models import build_source_sections, display_value, safe_html_text


def source(identifier: int, rank: int, *, mock: bool = False) -> CitationSource:
    return CitationSource(
        identifier, f"context-{identifier}", "doc", f"chunk-{identifier}",
        "<script>Unsafe title</script>", "Section", None, None, None, None,
        rank, None, "<b>Unsafe excerpt</b>", mock,
    )


def context(identifier: int, rank: int, *, mock: bool = False) -> ContextRow:
    return ContextRow(
        rank, None, None, None, "doc", None, f"chunk-{identifier}", "Title",
        None, None, None, None, "text", "preview", mock,
    )


def test_source_sections_keep_cited_rail_and_additional_context_separate() -> None:
    sections = build_source_sections((source(1, 4),), (context(1, 4), context(2, 2)))
    assert [card.citation_id for card in sections.cited] == [1]
    assert [(row.chunk_id, row.rank) for row in sections.additional] == [("chunk-2", 2)]
    assert sections.cited[0].rank == 4  # citation ID is not retrieval rank
    assert sections.cited[0].score is None


def test_mock_label_and_per_turn_ids_are_preserved() -> None:
    first = build_source_sections((source(1, 7, mock=True),), ())
    second = build_source_sections((source(1, 2, mock=True),), ())
    assert first.cited[0].is_mock and second.cited[0].is_mock
    assert first.cited[0].citation_id == second.cited[0].citation_id == 1


def test_untrusted_display_text_is_escaped_and_missing_values_are_na() -> None:
    escaped = safe_html_text('<script>alert("x")</script>')
    assert "<script>" not in escaped and "&lt;script&gt;" in escaped
    assert display_value(None) == "N/A" and display_value("") == "N/A"
    assert display_value(0) == "0"
