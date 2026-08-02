"""Pure view-model and bounded in-session conversation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence
from urllib.parse import parse_qsl, urlsplit

from generation.citations import CitationReference, CitationSource, EvidenceSpan

MAX_CONVERSATION_TURNS = 10


@dataclass(frozen=True)
class AnswerSegment:
    text: str
    citation_id: int | None = None


@dataclass(frozen=True)
class AnswerLine:
    segments: tuple[AnswerSegment, ...]
    blank: bool = False


@dataclass(frozen=True)
class SourceCard:
    citation_id: int
    title: str
    detail: str | None
    preview: str
    full_text: str
    rank: int
    score: float | None
    source_path: str | None
    url: str | None
    document_id: str | None
    chunk_id: str | None
    page: str | int | None
    is_mock: bool
    evidence: EvidenceSpan | None = None


@dataclass(frozen=True)
class ConversationTurn:
    question: str
    response: object
    turn_id: int | None = None


@dataclass(frozen=True)
class SourceSelection:
    turn_id: int
    citation_id: int
    viewer_open: bool = False

    def to_state(self) -> dict[str, int | bool]:
        return {"turn_id": self.turn_id, "citation_id": self.citation_id, "viewer_open": self.viewer_open}


@dataclass(frozen=True)
class SourceActions:
    view_label: str = "View source"
    original_url: str | None = None
    original_label: str | None = None


def build_answer_segments(answer: str, references: Sequence[CitationReference]) -> tuple[AnswerSegment, ...]:
    segments: list[AnswerSegment] = []
    cursor = 0
    for reference in sorted(references, key=lambda item: (item.answer_start or 0, item.answer_end or 0)):
        if reference.answer_start is None or reference.answer_end is None or reference.answer_start < cursor:
            continue
        if reference.answer_start > cursor:
            segments.append(AnswerSegment(answer[cursor:reference.answer_start]))
        segments.append(AnswerSegment(reference.marker, reference.citation_id))
        cursor = reference.answer_end
    if cursor < len(answer):
        segments.append(AnswerSegment(answer[cursor:]))
    return tuple(segments or [AnswerSegment(answer)])


def build_answer_lines(
    answer: str, references: Sequence[CitationReference],
) -> tuple[AnswerLine, ...]:
    """Preserve answer lines while replacing validated markers with control segments."""
    lines: list[AnswerLine] = []
    cursor = 0
    for raw_line in answer.splitlines(keepends=True):
        text = raw_line.rstrip("\r\n")
        line_end = cursor + len(text)
        line_refs = tuple(
            CitationReference(
                item.citation_id, item.marker,
                item.answer_start - cursor if item.answer_start is not None else None,
                item.answer_end - cursor if item.answer_end is not None else None,
                item.evidence,
            )
            for item in references
            if item.answer_start is not None and item.answer_end is not None
            and cursor <= item.answer_start < item.answer_end <= line_end
        )
        lines.append(AnswerLine(build_answer_segments(text, line_refs), blank=not text))
        cursor += len(raw_line)
    if not lines:
        lines.append(AnswerLine((AnswerSegment(answer),), blank=not answer))
    return tuple(lines)


def build_source_cards(sources: Sequence[CitationSource], *, preview_chars: int = 240) -> tuple[SourceCard, ...]:
    cards: list[SourceCard] = []
    for source in sources:
        detail = " · ".join(value for value in (source.article, source.section) if value) or None
        text = source.text
        preview = text if len(text) <= preview_chars else text[: max(0, preview_chars - 1)].rstrip() + "…"
        cards.append(SourceCard(
            source.citation_id, source.title or source.document_id or source.chunk_id or f"Retrieved source {source.citation_id}",
            detail, preview, text, source.rank, source.score, source.source_path, source.url,
            source.document_id, source.chunk_id, source.page, source.is_mock,
            source.evidence,
        ))
    return tuple(cards)


def append_conversation_turn(
    turns: Sequence[ConversationTurn], turn: ConversationTurn, *, maximum: int = MAX_CONVERSATION_TURNS,
) -> list[ConversationTurn]:
    if maximum < 1:
        raise ValueError("maximum must be positive")
    return [*turns, turn][-maximum:]


def clear_conversation() -> list[ConversationTurn]:
    return []


def resolve_turn_citation(
    turns: Sequence[ConversationTurn], turn_id: int, citation_id: int,
) -> CitationSource | None:
    """Resolve a citation only within its owning turn; IDs restart per answer."""
    for index, turn in enumerate(turns, 1):
        stable_id = turn.turn_id if turn.turn_id is not None else index
        if stable_id != turn_id:
            continue
        sources = getattr(turn.response, "citation_sources", ())
        return next((source for source in sources if source.citation_id == citation_id), None)
    return None


def citation_control_key(turn_id: int, citation_id: int, occurrence: int) -> str:
    return f"citation-{turn_id}-{citation_id}-{occurrence}"


def parse_source_selection(value: Any) -> SourceSelection | None:
    if not isinstance(value, Mapping):
        return None
    turn_id, citation_id = value.get("turn_id"), value.get("citation_id")
    if (
        not isinstance(turn_id, int) or isinstance(turn_id, bool) or turn_id < 1
        or not isinstance(citation_id, int) or isinstance(citation_id, bool) or citation_id < 1
    ):
        return None
    return SourceSelection(turn_id, citation_id, bool(value.get("viewer_open", False)))


def select_source_for_turn(
    sources: Sequence[CitationSource], turn_id: int, citation_id: int, *, viewer_open: bool = False,
) -> SourceSelection | None:
    """Create selection state only for a citation carried by the current turn."""
    candidate = parse_source_selection({
        "turn_id": turn_id,
        "citation_id": citation_id,
        "viewer_open": viewer_open,
    })
    if candidate is None:
        return None
    if not any(source.citation_id == citation_id for source in sources):
        return None
    return candidate


def clear_source_selection(state: MutableMapping[str, Any]) -> None:
    """Clear source UI state without modifying the owning conversation."""
    state["selected_source"] = None


def build_source_actions(source: CitationSource) -> SourceActions:
    url = None if source.is_mock else _validated_external_url(source.url)
    return SourceActions(
        original_url=url,
        original_label="Open original document ↗" if url else None,
    )


def _validated_external_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        blocked = ("key", "token", "secret", "password", "credential", "signature", "authorization")
        if any(any(marker in key.casefold() for marker in blocked) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
            return None
    except ValueError:
        return None
    return value


__all__ = ["AnswerLine", "AnswerSegment", "ConversationTurn", "MAX_CONVERSATION_TURNS",
           "SourceActions", "SourceCard", "SourceSelection", "append_conversation_turn",
           "build_answer_lines", "build_answer_segments", "build_source_actions",
           "build_source_cards", "citation_control_key", "clear_conversation",
           "clear_source_selection", "parse_source_selection", "resolve_turn_citation",
           "select_source_for_turn"]
