from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from retrieval.io_utils import clean_text

from .overlay_schema import AuthorityIndexEntry, DocumentOverlay, ValidityEvent
from .parser import DocumentNode


@dataclass(frozen=True)
class OverlayBundle:
    """Joined overlay tables keyed by document `id_str`."""

    document_overlays: dict[str, DocumentOverlay]
    validity_by_id: dict[str, tuple[ValidityEvent, ...]]
    authority_index: dict[str, tuple[AuthorityIndexEntry, ...]]


from .utils import as_bool, as_int


def parse_validity_event_row(row: dict[str, Any]) -> ValidityEvent:
    """Parse a raw validity timeline row into a typed event record."""

    return ValidityEvent(
        id_str=clean_text(row.get("id_str")),
        event_type=clean_text(row.get("event_type")),
        event_date_iso=clean_text(row.get("event_date_iso")),
        counterparty_id=clean_text(row.get("counterparty_id")),
        scope=clean_text(row.get("scope")),
        rel_canonical=clean_text(row.get("rel_canonical")),
        source_edge_id=clean_text(row.get("source_edge_id")),
        direction_verified=as_bool(row.get("direction_verified")),
    )


def parse_authority_index_row(row: dict[str, Any]) -> AuthorityIndexEntry:
    """Parse a raw authority index row into a typed entry."""

    return AuthorityIndexEntry(
        loai_van_ban=clean_text(row.get("loai_van_ban")),
        legal_authority_rank=as_int(row.get("legal_authority_rank"), 99),
        rank_label=clean_text(row.get("rank_label")),
        version=clean_text(row.get("version")),
    )


def parse_validity_event_rows(rows: Iterable[dict[str, Any]]) -> Iterator[ValidityEvent]:
    """Parse a stream of validity timeline rows."""

    for row in rows:
        yield parse_validity_event_row(row)


def parse_authority_index_rows(rows: Iterable[dict[str, Any]]) -> Iterator[AuthorityIndexEntry]:
    """Parse a stream of authority index rows."""

    for row in rows:
        yield parse_authority_index_row(row)


def index_validity_timeline(rows: Iterable[ValidityEvent]) -> dict[str, tuple[ValidityEvent, ...]]:
    """Index validity events by `id_str`, preserving stable chronological order."""

    by_id: dict[str, list[ValidityEvent]] = {}
    for event in rows:
        if not event.id_str:
            continue
        by_id.setdefault(event.id_str, []).append(event)
    out: dict[str, tuple[ValidityEvent, ...]] = {}
    for id_str, events in by_id.items():
        events.sort(key=lambda item: (item.event_date_iso, item.source_edge_id, item.counterparty_id))
        out[id_str] = tuple(events)
    return out


def index_authority_index(rows: Iterable[AuthorityIndexEntry]) -> dict[str, tuple[AuthorityIndexEntry, ...]]:
    """Index authority entries by document type."""

    by_type: dict[str, list[AuthorityIndexEntry]] = {}
    for entry in rows:
        if not entry.loai_van_ban:
            continue
        by_type.setdefault(entry.loai_van_ban, []).append(entry)
    return {key: tuple(values) for key, values in by_type.items()}


def compute_currency_status(id_str: str, events: Iterable[ValidityEvent], as_of_date: str | None = None) -> str:
    """Fold validity events into a coarse currency status.

    The result is a status label suitable for graph-guided filtering. This is a
    derived view and does not overwrite any node data.
    """

    ordered = [event for event in events if event.id_str == id_str and event.direction_verified]
    if not ordered:
        return "unknown"

    ordered.sort(key=lambda item: (item.event_date_iso, item.source_edge_id, item.counterparty_id))
    status = "unknown"
    for event in ordered:
        if as_of_date and event.event_date_iso and event.event_date_iso > as_of_date:
            continue
        status = _event_type_to_currency_status(event.event_type)
    return status


def resolve_authority_rank_conflicts(
    document_type: str,
    candidates: Iterable[AuthorityIndexEntry],
    fallback_rank: int = 99,
) -> AuthorityIndexEntry:
    """Resolve multiple authority index entries using lowest rank then newest version."""

    materialized = [entry for entry in candidates if entry.loai_van_ban == document_type]
    if not materialized:
        return AuthorityIndexEntry(loai_van_ban=document_type, legal_authority_rank=fallback_rank, rank_label="Unknown / unranked", version="fallback")

    def _parse_version(version_str: str) -> int:
        try:
            return int(version_str.split("@")[-1])
        except (ValueError, IndexError):
            return 0

    materialized.sort(key=lambda item: (item.legal_authority_rank, _parse_version(item.version)), reverse=False)
    best_rank = min(entry.legal_authority_rank for entry in materialized)
    best_candidates = [entry for entry in materialized if entry.legal_authority_rank == best_rank]
    best_candidates.sort(key=lambda item: _parse_version(item.version), reverse=True)
    return best_candidates[0]



class OverlayJoiner:
    """Join validity and authority overlays onto documents without mutating them."""

    def build_bundle(
        self,
        *,
        documents: Iterable[DocumentNode],
        validity_events: Iterable[ValidityEvent],
        authority_entries: Iterable[AuthorityIndexEntry],
        as_of_date: str | None = None,
    ) -> OverlayBundle:
        """Build a joined overlay bundle keyed by document `id_str`."""

        document_list = list(documents)
        validity_index = index_validity_timeline(validity_events)
        authority_index = index_authority_index(authority_entries)

        document_overlays: dict[str, DocumentOverlay] = {}
        for document in document_list:
            events = validity_index.get(document.id_str, ())
            candidates = authority_index.get(document.loai_van_ban, ())
            resolved = resolve_authority_rank_conflicts(document.loai_van_ban, candidates)
            document_overlays[document.id_str] = DocumentOverlay(
                id_str=document.id_str,
                currency_status=compute_currency_status(document.id_str, events, as_of_date=as_of_date),
                currency_status_as_of=as_of_date or "today",
                legal_authority_rank=resolved.legal_authority_rank,
                authority_rank_source=resolved.version,
                validity_events=events,
                authority_candidates=candidates,
            )

        return OverlayBundle(
            document_overlays=document_overlays,
            validity_by_id=validity_index,
            authority_index=authority_index,
        )

    def join_validity_overlay(
        self,
        documents: Iterable[DocumentNode],
        validity_events: Iterable[ValidityEvent],
        as_of_date: str | None = None,
    ) -> dict[str, DocumentOverlay]:
        """Return document overlays with validity status joined in."""

        bundle = self.build_bundle(
            documents=documents,
            validity_events=validity_events,
            authority_entries=(),
            as_of_date=as_of_date,
        )
        return bundle.document_overlays

    def join_authority_overlay(
        self,
        documents: Iterable[DocumentNode],
        authority_entries: Iterable[AuthorityIndexEntry],
    ) -> dict[str, DocumentOverlay]:
        """Return document overlays with authority rank joined in."""

        bundle = self.build_bundle(
            documents=documents,
            validity_events=(),
            authority_entries=authority_entries,
            as_of_date=None,
        )
        return bundle.document_overlays


def _event_type_to_currency_status(event_type: str) -> str:
    """Map a timeline event type to a coarse currency status label."""

    normalized = clean_text(event_type).lower()
    if normalized in {"enacted", "effective"}:
        return "active"
    if normalized in {"expired", "replaced"}:
        return "expired"
    if normalized in {"amended", "partially_amended"}:
        return "partial"
    if normalized in {"suspended", "partially_suspended"}:
        return "suspended"
    if normalized in {"partially_expired", "partially_replaced"}:
        return "partial"
    return "unknown"
