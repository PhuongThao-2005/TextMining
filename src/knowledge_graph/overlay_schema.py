from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidityEvent:
    """One derived validity event from `validity_timeline.jsonl`."""

    id_str: str
    event_type: str
    event_date_iso: str
    counterparty_id: str
    scope: str
    rel_canonical: str
    source_edge_id: str
    direction_verified: bool


@dataclass(frozen=True)
class AuthorityIndexEntry:
    """Versioned legal-authority rank entry from `authority_index.jsonl`."""

    loai_van_ban: str
    legal_authority_rank: int
    rank_label: str
    version: str


@dataclass(frozen=True)
class DocumentOverlay:
    """Joined overlay view for a single document."""

    id_str: str
    currency_status: str
    currency_status_as_of: str
    legal_authority_rank: int
    authority_rank_source: str
    validity_events: tuple[ValidityEvent, ...] = field(default_factory=tuple)
    authority_candidates: tuple[AuthorityIndexEntry, ...] = field(default_factory=tuple)

