from types import SimpleNamespace

from generation.citations import CitationReference, CitationSource
from service.ui_models import (
    ConversationTurn, append_conversation_turn, build_answer_lines, build_answer_segments,
    build_source_cards, citation_control_key, clear_conversation,
)


def source(identifier: int, *, title=None, text="Evidence") -> CitationSource:
    return CitationSource(identifier, f"ctx-{identifier}", None, f"chunk-{identifier}", title, None, None, None, None, None, identifier + 2, .7, text)


def test_answer_segmentation_preserves_badge_order() -> None:
    answer = "Alpha [1] beta [2]."
    references = (CitationReference(1, "[1]", 6, 9), CitationReference(2, "[2]", 15, 18))
    segments = build_answer_segments(answer, references)
    assert "".join(item.text for item in segments) == answer
    assert [item.citation_id for item in segments if item.citation_id] == [1, 2]


def test_cited_answer_lines_expose_control_segments_without_links_or_html() -> None:
    answer = "Alpha [1] beta [2]."
    references = (CitationReference(1, "[1]", 6, 9), CitationReference(2, "[2]", 15, 18))
    lines = build_answer_lines(answer, references)
    rendered = "".join(segment.text for line in lines for segment in line.segments)
    assert rendered == answer
    assert "href" not in rendered and "http" not in rendered and "<a" not in rendered
    assert citation_control_key(3, 1, 2) == "citation-3-1-2"


def test_answer_renderer_uses_segment_text_for_citation_button(monkeypatch) -> None:
    from src.ui import components

    labels: list[str] = []
    html_fragments: list[str] = []

    class Container:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class FakeStreamlit:
        @staticmethod
        def markdown(value, **__):
            html_fragments.append(str(value))
            return None

        @staticmethod
        def container(*_, **__):
            return Container()

        @staticmethod
        def button(label, **_):
            labels.append(label)
            return False

    monkeypatch.setattr(components, "st", FakeStreamlit())
    response = SimpleNamespace(
        answer="Supported claim [1].",
        citation_references=(CitationReference(1, "[1]", 16, 19),),
        citation_sources=(source(1),),
    )
    components.render_answer_article(response, 7)
    assert labels == ["[1]"]
    assert 'href="#source-7-1"' in "".join(html_fragments)


def test_source_cards_have_safe_fallback_and_truncated_preview() -> None:
    cards = build_source_cards([source(1, text="<script>alert(1)</script>" + "x" * 300)], preview_chars=30)
    assert cards[0].title == "chunk-1"
    assert len(cards[0].preview) == 30
    assert "<script>" in cards[0].full_text  # plain data; renderer uses st.text, never unsafe HTML


def test_display_sources_include_uncited_retrieved_contexts() -> None:
    from service.qa_service import ContextRow
    from src.ui import components

    cited = source(2, title="Cited", text="cited text")
    response = SimpleNamespace(
        citation_sources=(cited,),
        contexts=(
            ContextRow(4, None, None, None, None, None, "chunk-2", "Cited", None, None, None, None, "cited text", "cited", False),
            ContextRow(1, 0.8, 0.7, None, "doc-extra", "prov-extra", "chunk-extra", "Extra", "Article 5", None, "extra.pdf", None, "extra text", "extra", False),
        ),
    )

    display = components.display_sources_for_response(response)

    assert [item.citation_id for item in display] == [2, 3]
    assert display[1].title == "Extra"
    assert display[1].text == "extra text"


def test_document_metadata_rows_show_available_source_fields() -> None:
    from service.ui_models import build_source_cards
    from src.ui import components

    value = CitationSource(
        1, "ctx-1", "doc-1", "chunk-1", "Luật Việc làm", "Chương IV",
        "Điều 38", 7, "data/source.pdf", None, 2, 0.87654, "text",
        citation="Bộ luật Không số, 1994-06-23, Quốc hội: Lao động, Điều 76",
    )
    card = build_source_cards((value,))[0]
    row_pairs = components._document_metadata_rows(value, card, "vi")
    rows = dict(row_pairs)

    assert row_pairs[0] == ("Trích dẫn", "Bộ luật Không số, 1994-06-23, Quốc hội: Lao động, Điều 76")
    assert rows["Tên văn bản"] == "Luật Việc làm"
    assert rows["Điều"] == "Điều 38"
    assert rows["Mục/phần"] == "Chương IV"
    assert rows["Mã văn bản"] == "doc-1"
    assert rows["Mã đoạn"] == "chunk-1"
    assert rows["Hạng truy xuất"] == "2"
    assert rows["Điểm"] == "0.877"


def test_conversation_is_bounded_clearable_and_turn_local() -> None:
    turns = []
    for index in range(12):
        turns = append_conversation_turn(turns, ConversationTurn(f"q{index}", {"citation_sources": [source(1)]}))
    assert len(turns) == 10 and turns[0].question == "q2"
    assert clear_conversation() == []
    assert turns[0].response is not turns[1].response
