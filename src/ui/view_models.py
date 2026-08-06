"""Pure presentation view models shared by Streamlit components and tests."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Sequence

from generation.citations import CitationSource, EvidenceSpan, validate_evidence_span
from service.qa_service import ContextRow
from service.ui_models import SourceCard, build_source_cards


@dataclass(frozen=True)
class SourceSections:
    cited: tuple[SourceCard, ...]
    additional: tuple[ContextRow, ...]


@dataclass(frozen=True)
class SourceTextSegment:
    text: str
    highlighted: bool = False


@dataclass(frozen=True)
class SourceTextRender:
    segments: tuple[SourceTextSegment, ...]
    status: str
    label: str | None
    warning: str | None


def build_source_sections(
    cited_sources: Sequence[CitationSource], contexts: Sequence[ContextRow],
) -> SourceSections:
    cited_keys = {(source.chunk_id, source.rank) for source in cited_sources}
    additional = tuple(row for row in contexts if (row.chunk_id, row.rank) not in cited_keys)
    return SourceSections(build_source_cards(cited_sources), additional)


def resolve_source_text(source: CitationSource, contexts: Sequence[ContextRow]) -> str:
    """Return the exact full chunk already carried by the normalized response."""
    for row in contexts:
        if source.chunk_id and row.chunk_id == source.chunk_id and row.rank == source.rank:
            return row.text
        if (
            not source.chunk_id and source.document_id and row.document_id == source.document_id
            and row.rank == source.rank
        ):
            return row.text
    return source.text


def safe_html_text(value: Any) -> str:
    """Escape untrusted display text before application-owned HTML wrappers."""
    return escape(str(value), quote=True)


def build_source_text_segments(
    source_text: str, evidence_span: EvidenceSpan | None, *, context_id: str | None = None,
) -> SourceTextRender:
    """Split source text around a validated exact span; never guess a related sentence."""
    result = validate_evidence_span(source_text, evidence_span, context_id=context_id)
    if result.status != "valid" or result.span is None:
        return SourceTextRender((SourceTextSegment(source_text),), result.status, None, result.warning)
    start, end = result.span.start_char, result.span.end_char
    if start is None or end is None:
        return SourceTextRender((SourceTextSegment(source_text),), "invalid", None, "Validated evidence has no offsets.")
    segments = tuple(
        segment for segment in (
            SourceTextSegment(source_text[:start]),
            SourceTextSegment(source_text[start:end], True),
            SourceTextSegment(source_text[end:]),
        ) if segment.text
    )
    label = "Exact recorded evidence" if result.span.match_type == "explicit_offsets" else "Exact quote match"
    return SourceTextRender(segments, "valid", label, None)


def source_segments_html(render: SourceTextRender) -> str:
    """Render only escaped text inside application-owned presentation wrappers."""
    parts = []
    for segment in render.segments:
        escaped = safe_html_text(segment.text)
        parts.append(f'<span class="ga-evidence-highlight">{escaped}</span>' if segment.highlighted else escaped)
    return '<div class="ga-source-text">' + "".join(parts) + "</div>"


def display_value(value: Any) -> str:
    return "N/A" if value in (None, "") else str(value)


__all__ = ["SourceSections", "SourceTextRender", "SourceTextSegment", "build_source_sections",
           "build_source_text_segments", "display_value", "resolve_source_text", "safe_html_text",
           "source_segments_html"]
