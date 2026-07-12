from __future__ import annotations

from typing import Any

from .io_utils import clean_text


FILTERABLE_PAYLOAD_FIELDS = [
    "legal_authority_rank",
    "validity_group",
    "id_str",
    "unit_type",
    "loai_van_ban",
    "legal_field_code",
    "sector_code",
    "scope_code",
    "issuing_authority_code",
    "issue_year",
]


def facet_value(document: dict[str, Any], name: str, part: str, default: str = "") -> str:
    value = document.get(name)
    if isinstance(value, dict):
        return clean_text(value.get(part)) or default
    return default


def build_unit_ref(provision: dict[str, Any]) -> str:
    unit_type = clean_text(provision.get("unit_type"))
    article_number = clean_text(provision.get("article_number"))
    if unit_type == "article" and article_number:
        return f"Điều {article_number}"
    return unit_type


def build_retrieval_text(
    chunk: dict[str, Any],
    provision: dict[str, Any],
    document: dict[str, Any],
) -> str:
    """Build the exact v2 text that is embedded, not stored as payload."""

    unit_ref = build_unit_ref(provision)
    unit_heading = clean_text(provision.get("unit_heading"))
    unit_part = clean_text(f"{unit_ref} {unit_heading}")
    header_parts = [
        clean_text(document.get("title") or provision.get("title")),
        clean_text(document.get("citation_label") or provision.get("citation_label")),
        unit_part,
    ]
    header = " | ".join(part for part in header_parts if part)
    return f"{header}\n{clean_text(chunk.get('chunk_text'))}"


def build_payload(
    chunk: dict[str, Any],
    provision: dict[str, Any],
    document: dict[str, Any],
) -> dict[str, Any]:
    """Join chunk, provision, and document into the vector DB payload."""

    payload = {
        "chunk_id": clean_text(chunk.get("chunk_id")),
        "parent_unit_id": clean_text(chunk.get("parent_unit_id")),
        "id_str": clean_text(chunk.get("id_str")),
        "chunk_index_in_unit": int(chunk.get("chunk_index_in_unit") or 0),
        "chunk_count_in_unit": int(chunk.get("chunk_count_in_unit") or 0),
        "chunk_text": clean_text(chunk.get("chunk_text")),
        "chunk_char_count": int(chunk.get("chunk_char_count") or 0),
        "chunk_token_estimate": int(chunk.get("chunk_token_estimate") or 0),
        "unit_split": bool(chunk.get("unit_split", False)),
        "structuring_quality_flags": list(chunk.get("structuring_quality_flags") or []),
        "unit_type": clean_text(provision.get("unit_type")),
        "article_number": clean_text(provision.get("article_number")) or None,
        "unit_heading": clean_text(provision.get("unit_heading")),
        "path": clean_text(provision.get("path")),
        "citation_anchor": clean_text(provision.get("citation_anchor")),
        "title": clean_text(document.get("title") or provision.get("title")),
        "citation_label": clean_text(document.get("citation_label") or provision.get("citation_label")),
        "so_ky_hieu": clean_text(document.get("so_ky_hieu") or provision.get("so_ky_hieu")),
        "loai_van_ban": clean_text(document.get("loai_van_ban") or provision.get("loai_van_ban")),
        "legal_authority_rank": int(document.get("legal_authority_rank") or provision.get("legal_authority_rank") or 99),
        "validity_group": clean_text(document.get("validity_group") or provision.get("validity_group") or "unknown"),
        "currency_hint": clean_text(document.get("currency_hint") or provision.get("currency_hint")),
        "issuing_authority_code": facet_value(document, "issuing_authority", "code", "MISSING"),
        "issuing_authority_surface": facet_value(document, "issuing_authority", "surface"),
        "legal_field_code": facet_value(document, "legal_field", "code", "MISSING"),
        "legal_field_surface": facet_value(document, "legal_field", "surface"),
        "sector_code": facet_value(document, "sector", "code", "MISSING"),
        "sector_surface": facet_value(document, "sector", "surface"),
        "scope_code": facet_value(document, "scope", "code", "MISSING"),
        "scope_surface": facet_value(document, "scope", "surface"),
        "issue_year": document.get("issue_year"),
        "ngay_ban_hanh_iso": clean_text(document.get("ngay_ban_hanh_iso")),
        "ngay_co_hieu_luc_iso": clean_text(document.get("ngay_co_hieu_luc_iso")),
        "ngay_het_hieu_luc_iso": clean_text(document.get("ngay_het_hieu_luc_iso")),
        "quality_flags": list(document.get("quality_flags") or provision.get("quality_flags") or []),
    }
    if payload["issue_year"] is not None:
        payload["issue_year"] = int(payload["issue_year"])
    return payload
