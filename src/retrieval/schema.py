from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_FILTER_PROFILES = {"current_law", "broad", "historical", "graph_guided"}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    chunk_text: str
    citation_anchor: str
    citation_label: str
    title: str
    article_number: str | None
    unit_type: str
    path: str | None
    validity_group: str
    legal_authority_rank: int
    vector_score: float
    rerank_score: float
    id_str: str
    parent_unit_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    total_candidates: int
    filter_profile_used: str
    empty_filter_warning: bool = False


@dataclass(frozen=True)
class VectorRecord:
    point_id: str
    vector: list[float]
    payload: dict[str, Any]
