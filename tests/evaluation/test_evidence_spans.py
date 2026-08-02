from html import unescape

import pytest

from generation.citations import (
    EvidenceCapability, EvidenceSpan, detect_evidence_capability, validate_evidence_span,
)
from src.ui.styles import build_application_css
from src.ui.view_models import build_source_text_segments, source_segments_html


def span(**overrides: object) -> EvidenceSpan:
    values = {
        "context_id": "chunk-1", "start_char": 6, "end_char": 11,
        "quote": "world", "match_type": "explicit_offsets",
    }
    values.update(overrides)
    return EvidenceSpan(**values)  # type: ignore[arg-type]


def test_valid_explicit_offsets_and_exact_unique_quote() -> None:
    explicit = validate_evidence_span("hello world", span(), context_id="chunk-1")
    assert explicit.status == "valid" and explicit.span == span()
    quoted = validate_evidence_span(
        "before exact quote after",
        EvidenceSpan("chunk-1", quote="exact quote", match_type="exact_unique_quote"),
        context_id="chunk-1",
    )
    assert quoted.status == "valid"
    assert quoted.span and (quoted.span.start_char, quoted.span.end_char) == (7, 18)


@pytest.mark.parametrize("evidence", [
    span(start_char=-1), span(end_char=99), span(start_char=6, end_char=6),
    span(quote="wrong"), span(context_id="stale-chunk"),
])
def test_invalid_or_stale_offsets_are_rejected(evidence: EvidenceSpan) -> None:
    result = validate_evidence_span("hello world", evidence, context_id="chunk-1")
    assert result.status == "invalid" and result.span is None


def test_duplicate_quote_is_not_highlighted_without_position_metadata() -> None:
    evidence = EvidenceSpan("chunk-1", quote="repeat", match_type="exact_unique_quote")
    result = validate_evidence_span("repeat and repeat", evidence, context_id="chunk-1")
    assert result.status == "invalid" and "not unique" in (result.warning or "")


def test_absent_evidence_is_available_source_not_invalid_span() -> None:
    result = validate_evidence_span("source", None, context_id="chunk-1")
    assert result.status == "unavailable" and result.warning is None


def test_unicode_and_line_breaks_preserve_source_exactly() -> None:
    text = "Mở đầu\nBằng chứng tiếng Việt\nKết thúc"
    quote = "Bằng chứng tiếng Việt"
    start = text.index(quote)
    render = build_source_text_segments(
        text, EvidenceSpan("chunk-1", start, start + len(quote), quote, "explicit_offsets"),
        context_id="chunk-1",
    )
    assert "".join(item.text for item in render.segments) == text
    assert [item.text for item in render.segments if item.highlighted] == [quote]


def test_highlight_html_escapes_untrusted_source_and_marks_only_evidence() -> None:
    text = '<script>alert("x")</script> safe evidence'
    quote = "safe evidence"
    start = text.index(quote)
    render = build_source_text_segments(
        text, EvidenceSpan("chunk-1", start, len(text), quote, "explicit_offsets"),
        context_id="chunk-1",
    )
    html = source_segments_html(render)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert html.count('class="ga-evidence-highlight"') == 1
    visible = unescape(html.replace('<div class="ga-source-text">', "").replace("</div>", "")
                       .replace('<span class="ga-evidence-highlight">', "").replace("</span>", ""))
    assert visible == text


def test_invalid_evidence_produces_plain_unhighlighted_segments() -> None:
    render = build_source_text_segments("hello world", span(quote="stale"), context_id="chunk-1")
    assert render.status == "invalid"
    assert len(render.segments) == 1 and not render.segments[0].highlighted


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({"structured_citations": True, "explicit_offsets": True}, EvidenceCapability.EXACT_SPANS_SUPPORTED),
    ({"structured_citations": True, "exact_quotes": True}, EvidenceCapability.EXACT_QUOTES_SUPPORTED),
    ({"structured_citations": True}, EvidenceCapability.SOURCE_MAPPING_ONLY),
    ({"structured_citations": False}, EvidenceCapability.NO_STRUCTURED_CITATIONS),
])
def test_production_capability_detection(kwargs: dict[str, bool], expected: EvidenceCapability) -> None:
    assert detect_evidence_capability(**kwargs) is expected


def test_light_and_dark_styles_include_controlled_evidence_highlight() -> None:
    for theme in ("Light", "Dark"):
        css = build_application_css(theme)
        assert ".ga-evidence-highlight" in css and "browser-default" not in css

