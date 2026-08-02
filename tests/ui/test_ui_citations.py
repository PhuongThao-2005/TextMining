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

    class Container:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class FakeStreamlit:
        @staticmethod
        def markdown(*_, **__):
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


def test_source_cards_have_safe_fallback_and_truncated_preview() -> None:
    cards = build_source_cards([source(1, text="<script>alert(1)</script>" + "x" * 300)], preview_chars=30)
    assert cards[0].title == "chunk-1"
    assert len(cards[0].preview) == 30
    assert "<script>" in cards[0].full_text  # plain data; renderer uses st.text, never unsafe HTML


def test_conversation_is_bounded_clearable_and_turn_local() -> None:
    turns = []
    for index in range(12):
        turns = append_conversation_turn(turns, ConversationTurn(f"q{index}", {"citation_sources": [source(1)]}))
    assert len(turns) == 10 and turns[0].question == "q2"
    assert clear_conversation() == []
    assert turns[0].response is not turns[1].response
