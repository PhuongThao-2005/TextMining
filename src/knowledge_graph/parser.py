from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from retrieval.io_utils import clean_text

from .schema import ChunkNode, DocumentNode, ExternalStubNode, FacetValue, ProvisionNode, TextProvenanceRecord


def _as_int(value: Any, default: int = 0) -> int:
    """Convert a JSON value to int with a stable default."""

    if value is None or value == "":
        return default
    return int(value)


def _as_bool(value: Any, default: bool = False) -> bool:
    """Convert a JSON value to bool with a stable default."""

    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _facet_value(value: Any) -> FacetValue:
    """Normalize a `{code, surface, raw}` facet object."""

    if isinstance(value, dict):
        code = clean_text(value.get("code")) or "MISSING"
        surface = clean_text(value.get("surface"))
        raw = clean_text(value.get("raw"))
        return FacetValue(code=code, surface=surface, raw=raw)
    return FacetValue(code="MISSING", surface="", raw="")


def _quality_flags(values: Any) -> tuple[str, ...]:
    """Normalize a JSON list of quality flags into an immutable tuple."""

    if not values:
        return ()
    return tuple(clean_text(item) for item in values if clean_text(item))


def parse_text_provenance_row(row: dict[str, Any]) -> TextProvenanceRecord:
    """Parse a `text_provenance.jsonl` row into a typed record."""

    return TextProvenanceRecord(
        id_str=clean_text(row.get("id_str")),
        text_status=clean_text(row.get("text_status")),
        structuring_status=clean_text(row.get("structuring_status")),
        legal_unit_count=_as_int(row.get("legal_unit_count")),
        chunk_count=_as_int(row.get("chunk_count")),
    )


def parse_document_row(
    row: dict[str, Any],
    provenance: TextProvenanceRecord | dict[str, Any] | None = None,
) -> DocumentNode:
    """Parse a raw document row into a graph-ready document node.

    Validity and authority overlays are intentionally excluded and are expected
    to be joined later from `validity_timeline.jsonl` and
    `authority_index.jsonl`.
    """

    provenance_record = _normalize_provenance(provenance)
    return DocumentNode(
        id_str=clean_text(row.get("id_str")),
        title=clean_text(row.get("title")),
        so_ky_hieu=clean_text(row.get("so_ky_hieu")),
        citation_label=clean_text(row.get("citation_label")),
        loai_van_ban=clean_text(row.get("loai_van_ban")),
        loai_van_ban_raw=clean_text(row.get("loai_van_ban_raw") or row.get("loai_van_ban")),
        issuing_authority=_facet_value(row.get("issuing_authority")),
        legal_field=_facet_value(row.get("legal_field")),
        sector=_facet_value(row.get("sector")),
        scope=_facet_value(row.get("scope")),
        ngay_ban_hanh_iso=clean_text(row.get("ngay_ban_hanh_iso")),
        ngay_co_hieu_luc_iso=clean_text(row.get("ngay_co_hieu_luc_iso")),
        ngay_het_hieu_luc_iso=clean_text(row.get("ngay_het_hieu_luc_iso")),
        issue_year=_coerce_optional_int(row.get("issue_year")),
        chuc_danh=clean_text(row.get("chuc_danh")),
        nguoi_ky=clean_text(row.get("nguoi_ky")),
        quality_flags=_quality_flags(row.get("quality_flags")),
        text_status=provenance_record.text_status,
        structuring_status=provenance_record.structuring_status,
        legal_unit_count=provenance_record.legal_unit_count,
        chunk_count=provenance_record.chunk_count,
    )


def parse_external_stub_row(row: dict[str, Any]) -> ExternalStubNode:
    """Parse an external stub row into a non-citable placeholder node."""

    return ExternalStubNode(
        id_str=clean_text(row.get("id_str")),
        is_external_stub=_as_bool(row.get("is_external_stub"), True),
        citation_safe=_as_bool(row.get("citation_safe"), False),
        referenced_by_edge_count=_as_int(row.get("referenced_by_edge_count")),
        quality_flags=_quality_flags(row.get("quality_flags")),
    )


def parse_provision_row(row: dict[str, Any]) -> ProvisionNode:
    """Parse a structural provision row.

    The returned record intentionally excludes validity and authority overlays.
    """

    return ProvisionNode(
        unit_id=clean_text(row.get("unit_id")),
        id_str=clean_text(row.get("id_str")),
        unit_type=clean_text(row.get("unit_type")),
        article_number=clean_text(row.get("article_number")) or None,
        unit_heading=clean_text(row.get("unit_heading")),
        path=clean_text(row.get("path")),
        citation_anchor=clean_text(row.get("citation_anchor")),
        char_start=_as_int(row.get("char_start")),
        char_end=_as_int(row.get("char_end")),
        unit_char_count=_as_int(row.get("unit_char_count")),
        unit_token_estimate=_as_int(row.get("unit_token_estimate")),
        chunk_count=_as_int(row.get("chunk_count")),
        coverage_verified=_as_bool(row.get("coverage_verified")),
        title=clean_text(row.get("title")) or None,
        citation_label=clean_text(row.get("citation_label")) or None,
        loai_van_ban=clean_text(row.get("loai_van_ban")) or None,
        so_ky_hieu=clean_text(row.get("so_ky_hieu")) or None,
        quality_flags=_quality_flags(row.get("quality_flags")),
    )


def parse_chunk_row(row: dict[str, Any]) -> ChunkNode:
    """Parse a retrieval chunk row into a slim pointer node."""

    return ChunkNode(
        chunk_id=clean_text(row.get("chunk_id")),
        parent_unit_id=clean_text(row.get("parent_unit_id")),
        id_str=clean_text(row.get("id_str")),
        chunk_index_in_unit=_as_int(row.get("chunk_index_in_unit")),
        chunk_count_in_unit=_as_int(row.get("chunk_count_in_unit")),
        unit_split=_as_bool(row.get("unit_split")),
        structuring_quality_flags=_quality_flags(row.get("structuring_quality_flags")),
    )


def parse_document_rows(
    rows: Iterable[dict[str, Any]],
    provenance_by_id: dict[str, TextProvenanceRecord | dict[str, Any]] | None = None,
) -> Iterator[DocumentNode]:
    """Parse a stream of document rows, optionally joining text provenance."""

    provenance_by_id = provenance_by_id or {}
    for row in rows:
        id_str = clean_text(row.get("id_str"))
        yield parse_document_row(row, provenance_by_id.get(id_str))


def parse_external_stub_rows(rows: Iterable[dict[str, Any]]) -> Iterator[ExternalStubNode]:
    """Parse a stream of external stub rows."""

    for row in rows:
        yield parse_external_stub_row(row)


def parse_provision_rows(rows: Iterable[dict[str, Any]]) -> Iterator[ProvisionNode]:
    """Parse a stream of provision rows."""

    for row in rows:
        yield parse_provision_row(row)


def parse_chunk_rows(rows: Iterable[dict[str, Any]]) -> Iterator[ChunkNode]:
    """Parse a stream of chunk rows."""

    for row in rows:
        yield parse_chunk_row(row)


def index_text_provenance(rows: Iterable[dict[str, Any]]) -> dict[str, TextProvenanceRecord]:
    """Build an `id_str` index of text provenance records."""

    out: dict[str, TextProvenanceRecord] = {}
    for row in rows:
        record = parse_text_provenance_row(row)
        if record.id_str:
            out[record.id_str] = record
    return out


def _normalize_provenance(provenance: TextProvenanceRecord | dict[str, Any] | None) -> TextProvenanceRecord:
    """Normalize optional provenance input into a typed record."""

    if provenance is None:
        return TextProvenanceRecord(
            id_str="",
            text_status="",
            structuring_status="",
            legal_unit_count=0,
            chunk_count=0,
        )
    if isinstance(provenance, TextProvenanceRecord):
        return provenance
    return parse_text_provenance_row(provenance)


def _coerce_optional_int(value: Any) -> int | None:
    """Convert a JSON value to an optional integer."""

    if value is None or value == "":
        return None
    return int(value)