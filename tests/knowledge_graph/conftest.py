from __future__ import annotations

import json
from pathlib import Path
import pytest

from knowledge_graph import (
    DocumentNode,
    ExternalStubNode,
    ProvisionNode,
    ChunkNode,
    GraphEdge,
    FacetValue,
)


@pytest.fixture
def mock_dataset_dir(tmp_path: Path) -> Path:
    """Fixture that creates a temporary directory with a mock v2 dataset."""
    
    # 1. Documents
    docs = [
        {
            "id_str": "1",
            "title": "Doc 1 Title",
            "so_ky_hieu": "01/DOC",
            "citation_label": "Doc 1 Citation",
            "loai_van_ban": "Luật",
            "loai_van_ban_raw": "Luật",
            "legal_authority_rank": 2,
            "issuing_authority": {"code": "QH", "surface": "Quốc hội", "raw": "Quốc hội"},
            "legal_field": {"code": "ADMIN", "surface": "Hành chính", "raw": "Hành chính"},
            "sector": {"code": "SEC1", "surface": "Sector 1", "raw": "Sector 1"},
            "scope": {"code": "NATIONAL", "surface": "Quốc gia", "raw": "Quốc gia"},
            "ngay_ban_hanh_iso": "2026-01-01",
            "ngay_co_hieu_luc_iso": "2026-02-01",
            "ngay_het_hieu_luc_iso": None,
            "issue_year": 2026,
            "chuc_danh": "Chủ tịch Quốc hội",
            "nguoi_ky": "Nguyen Van A",
            "quality_flags": [],
        },
        {
            "id_str": "2",
            "title": "Doc 2 Title",
            "so_ky_hieu": "02/DOC",
            "citation_label": "Doc 2 Citation",
            "loai_van_ban": "Nghị định",
            "loai_van_ban_raw": "Nghị định",
            "legal_authority_rank": 4,
            "issuing_authority": {"code": "CP", "surface": "Chính phủ", "raw": "Chính phủ"},
            "legal_field": {"code": "ADMIN", "surface": "Hành chính", "raw": "Hành chính"},
            "sector": {"code": "SEC1", "surface": "Sector 1", "raw": "Sector 1"},
            "scope": {"code": "NATIONAL", "surface": "Quốc gia", "raw": "Quốc gia"},
            "ngay_ban_hanh_iso": "2026-03-01",
            "ngay_co_hieu_luc_iso": "2026-04-01",
            "ngay_het_hieu_luc_iso": None,
            "issue_year": 2026,
            "chuc_danh": "Thủ tướng Chính phủ",
            "nguoi_ky": "Tran Van B",
            "quality_flags": [],
        }
    ]
    docs_file = tmp_path / "documents.jsonl"
    with open(docs_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")

    # 2. Provisions
    provisions = [
        {
            "unit_id": "1::article::1",
            "id_str": "1",
            "unit_type": "article",
            "article_number": "1",
            "unit_heading": "Điều 1: Phạm vi",
            "path": "article::1",
            "citation_anchor": "Điều 1",
            "char_start": 0,
            "char_end": 100,
            "unit_char_count": 100,
            "unit_token_estimate": 25,
            "chunk_count": 1,
            "coverage_verified": True,
        },
        {
            "unit_id": "1::article::2",
            "id_str": "1",
            "unit_type": "article",
            "article_number": "2",
            "unit_heading": "Điều 2: Định nghĩa",
            "path": "article::2",
            "citation_anchor": "Điều 2",
            "char_start": 101,
            "char_end": 200,
            "unit_char_count": 99,
            "unit_token_estimate": 24,
            "chunk_count": 1,
            "coverage_verified": True,
        },
        {
            "unit_id": "2::article::1",
            "id_str": "2",
            "unit_type": "article",
            "article_number": "1",
            "unit_heading": "Điều 1: Hướng dẫn",
            "path": "article::1",
            "citation_anchor": "Điều 1",
            "char_start": 0,
            "char_end": 120,
            "unit_char_count": 120,
            "unit_token_estimate": 30,
            "chunk_count": 1,
            "coverage_verified": True,
        }
    ]
    prov_file = tmp_path / "provisions.jsonl"
    with open(prov_file, "w", encoding="utf-8") as f:
        for prov in provisions:
            f.write(json.dumps(prov) + "\n")

    # 3. Chunks
    chunks = [
        {
            "chunk_id": "1::article::1::chunk::1",
            "parent_unit_id": "1::article::1",
            "id_str": "1",
            "chunk_index_in_unit": 1,
            "chunk_count_in_unit": 1,
            "unit_split": False,
            "chunk_text": "Phạm vi điều chỉnh của Luật này...",
            "chunk_char_count": 100,
            "chunk_token_estimate": 25,
            "char_start": 0,
            "char_end": 100,
            "structuring_quality_flags": [],
        },
        {
            "chunk_id": "1::article::2::chunk::1",
            "parent_unit_id": "1::article::2",
            "id_str": "1",
            "chunk_index_in_unit": 1,
            "chunk_count_in_unit": 1,
            "unit_split": False,
            "chunk_text": "Định nghĩa các thuật ngữ chính...",
            "chunk_char_count": 99,
            "chunk_token_estimate": 24,
            "char_start": 0,
            "char_end": 99,
            "structuring_quality_flags": [],
        },
        {
            "chunk_id": "2::article::1::chunk::1",
            "parent_unit_id": "2::article::1",
            "id_str": "2",
            "chunk_index_in_unit": 1,
            "chunk_count_in_unit": 1,
            "unit_split": False,
            "chunk_text": "Nghị định này hướng dẫn chi tiết...",
            "chunk_char_count": 120,
            "chunk_token_estimate": 30,
            "char_start": 0,
            "char_end": 120,
            "structuring_quality_flags": [],
        }
    ]
    chunks_file = tmp_path / "chunks.jsonl"
    with open(chunks_file, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")

    # 4. Edges
    edges = [
        {
            "edge_id": "2->1::Van ban huong dan",
            "src_id": "2",
            "dst_id": "1",
            "rel_canonical": "guides_or_details",
            "rel_group": "guidance",
            "rel_raw": "Văn bản hướng dẫn",
            "direction_normalized": True,
            "direction_verified": True,
            "external_target": False,
            "edge_quality_flags": [],
            "provenance": {"doc_id": "2", "other_doc_id": "1", "relationship": "Văn bản hướng dẫn"}
        },
        {
            "edge_id": "1->3::Van ban can cu",
            "src_id": "1",
            "dst_id": "3",
            "rel_canonical": "based_on",
            "rel_group": "basis",
            "rel_raw": "Văn bản căn cứ",
            "direction_normalized": True,
            "direction_verified": True,
            "external_target": True,
            "edge_quality_flags": [],
            "provenance": {"doc_id": "1", "other_doc_id": "3", "relationship": "Văn bản căn cứ"}
        },
        {
            "edge_id": "2->4::Van ban lien quan",
            "src_id": "2",
            "dst_id": "4",
            "rel_canonical": "related_to",
            "rel_group": "related",
            "rel_raw": "Văn bản liên quan",
            "direction_normalized": False,
            "direction_verified": False,
            "external_target": True,
            "edge_quality_flags": [],
            "provenance": {"doc_id": "2", "other_doc_id": "4", "relationship": "Văn bản liên quan"}
        }
    ]
    edges_file = tmp_path / "edges.jsonl"
    with open(edges_file, "w", encoding="utf-8") as f:
        for edge in edges:
            f.write(json.dumps(edge) + "\n")

    # 5. External Stubs
    stubs = [
        {
            "id_str": "3",
            "is_external_stub": True,
            "citation_safe": False,
            "referenced_by_edge_count": 1,
            "quality_flags": ["external_stub"]
        },
        {
            "id_str": "4",
            "is_external_stub": True,
            "citation_safe": False,
            "referenced_by_edge_count": 1,
            "quality_flags": ["external_stub"]
        }
    ]
    stubs_file = tmp_path / "external_stubs.jsonl"
    with open(stubs_file, "w", encoding="utf-8") as f:
        for stub in stubs:
            f.write(json.dumps(stub) + "\n")

    # 6. Text Provenance
    prov_records = [
        {
            "id_str": "1",
            "text_status": "available",
            "structuring_status": "structured_by_article",
            "legal_unit_count": 2,
            "chunk_count": 2
        },
        {
            "id_str": "2",
            "text_status": "available",
            "structuring_status": "structured_by_article",
            "legal_unit_count": 1,
            "chunk_count": 1
        }
    ]
    prov_rec_file = tmp_path / "text_provenance.jsonl"
    with open(prov_rec_file, "w", encoding="utf-8") as f:
        for rec in prov_records:
            f.write(json.dumps(rec) + "\n")

    return tmp_path


@pytest.fixture
def mock_document_node() -> DocumentNode:
    """Fixture that returns a populated DocumentNode."""
    return DocumentNode(
        id_str="1",
        title="Test Document",
        so_ky_hieu="123/TEST",
        citation_label="Test Doc Citation",
        loai_van_ban="Luật",
        loai_van_ban_raw="Luật",
        issuing_authority=FacetValue("QH", "Quốc hội", "Quốc hội"),
        legal_field=FacetValue("ADMIN", "Hành chính", "Hành chính"),
        sector=FacetValue("SEC1", "Sector 1", "Sector 1"),
        scope=FacetValue("NATIONAL", "Quốc gia", "Quốc gia"),
        ngay_ban_hanh_iso="2026-01-01",
        ngay_co_hieu_luc_iso="2026-02-01",
        ngay_het_hieu_luc_iso="2027-01-01",
        issue_year=2026,
        chuc_danh="Chủ tịch",
        nguoi_ky="Ky Nguoi",
        quality_flags=("expired_full",),
        text_status="available",
        structuring_status="structured_by_article",
        legal_unit_count=1,
        chunk_count=1,
    )


@pytest.fixture
def mock_external_stub_node() -> ExternalStubNode:
    """Fixture that returns a populated ExternalStubNode."""
    return ExternalStubNode(
        id_str="3",
        is_external_stub=True,
        citation_safe=False,
        referenced_by_edge_count=1,
        quality_flags=("external_stub",),
    )


@pytest.fixture
def mock_provision_node() -> ProvisionNode:
    """Fixture that returns a populated ProvisionNode."""
    return ProvisionNode(
        unit_id="1::article::1",
        id_str="1",
        unit_type="article",
        article_number="1",
        unit_heading="Điều 1",
        path="article::1",
        citation_anchor="Điều 1",
        char_start=0,
        char_end=100,
        unit_char_count=100,
        unit_token_estimate=25,
        chunk_count=1,
        coverage_verified=True,
    )


@pytest.fixture
def mock_chunk_node() -> ChunkNode:
    """Fixture that returns a populated ChunkNode."""
    return ChunkNode(
        chunk_id="1::article::1::chunk::1",
        parent_unit_id="1::article::1",
        id_str="1",
        chunk_index_in_unit=1,
        chunk_count_in_unit=1,
        unit_split=False,
        structuring_quality_flags=(),
    )


@pytest.fixture
def mock_graph_edge() -> GraphEdge:
    """Fixture that returns a populated GraphEdge."""
    return GraphEdge(
        edge_id="2->1::Van ban huong dan",
        src_id="2",
        dst_id="1",
        rel_canonical="guides_or_details",
        rel_group="guidance",
        rel_raw="Văn bản hướng dẫn",
        direction_normalized=True,
        direction_verified=True,
        external_target=False,
        edge_quality_flags=(),
        provenance={},
    )
