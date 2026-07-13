from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FacetValue:
    """Normalized `{code, surface, raw}` facet triple."""

    code: str
    surface: str
    raw: str


@dataclass(frozen=True)
class TextProvenanceRecord:
    """Normalized text provenance values for a document."""

    id_str: str
    text_status: str
    structuring_status: str
    legal_unit_count: int
    chunk_count: int


@dataclass(frozen=True)
class DocumentNode:
    """Graph-ready document record without validity or authority overlays."""

    id_str: str
    title: str
    so_ky_hieu: str
    citation_label: str
    loai_van_ban: str
    loai_van_ban_raw: str
    issuing_authority: FacetValue
    legal_field: FacetValue
    sector: FacetValue
    scope: FacetValue
    ngay_ban_hanh_iso: str
    ngay_co_hieu_luc_iso: str
    ngay_het_hieu_luc_iso: str
    issue_year: int | None
    chuc_danh: str
    nguoi_ky: str
    quality_flags: tuple[str, ...]
    text_status: str | None = None
    structuring_status: str | None = None
    legal_unit_count: int | None = None
    chunk_count: int | None = None


@dataclass(frozen=True)
class ExternalStubNode:
    """Non-citable placeholder for an external document target."""

    id_str: str
    is_external_stub: bool
    citation_safe: bool
    referenced_by_edge_count: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class ProvisionNode:
    """Citation-level structural node inside a document."""

    unit_id: str
    id_str: str
    unit_type: str
    article_number: str | None
    unit_heading: str
    path: str
    citation_anchor: str
    char_start: int
    char_end: int
    unit_char_count: int
    unit_token_estimate: int
    chunk_count: int
    coverage_verified: bool
    title: str | None = None
    citation_label: str | None = None
    loai_van_ban: str | None = None
    so_ky_hieu: str | None = None
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkNode:
    """Retrieval chunk pointer record."""

    chunk_id: str
    parent_unit_id: str
    id_str: str
    chunk_index_in_unit: int
    chunk_count_in_unit: int
    unit_split: bool
    structuring_quality_flags: tuple[str, ...]
