from __future__ import annotations



from knowledge_graph import (
    parse_document_row,
    parse_external_stub_row,
    parse_provision_row,
    parse_chunk_row,
    index_text_provenance,
    DocumentNode,
    ExternalStubNode,
    ProvisionNode,
    ChunkNode,
)


def test_parse_text_provenance():
    """Test text provenance record parser and index creation."""
    rows = [
        {"id_str": "1", "text_status": "available", "structuring_status": "structured_by_article", "legal_unit_count": 2, "chunk_count": 2},
        {"id_str": "2", "text_status": "missing", "structuring_status": "document_fallback", "legal_unit_count": 0, "chunk_count": 0}
    ]
    prov_index = index_text_provenance(rows)
    assert len(prov_index) == 2
    assert prov_index["1"].text_status == "available"
    assert prov_index["2"].chunk_count == 0


def test_parse_document_row():
    """Test that a valid document row is parsed correctly and provenance is joined."""
    row = {
        "id_str": " 1 ",
        "title": "Document Title",
        "so_ky_hieu": "10/SL",
        "citation_label": "Doc 10/SL",
        "loai_van_ban": "Sắc lệnh",
        "issuing_authority": {"code": "CHU_TICH", "surface": "Chủ tịch", "raw": "Chủ tịch"},
        "legal_field": None,
        "ngay_ban_hanh_iso": "1945-12-01",
        "issue_year": "1945",
        "quality_flags": ["missing_scope", "expired_full"]
    }
    
    prov_row = {
        "id_str": "1",
        "text_status": "available",
        "structuring_status": "structured_by_article",
        "legal_unit_count": 5,
        "chunk_count": 5
    }
    
    # Verify parsing succeeds and cleans strings
    doc = parse_document_row(row, provenance=prov_row)
    assert isinstance(doc, DocumentNode)
    assert doc.id_str == "1"
    assert doc.title == "Document Title"
    assert doc.loai_van_ban == "Sắc lệnh"
    assert doc.issuing_authority.code == "CHU_TICH"
    assert doc.legal_field.code == "MISSING" # default for null facet
    assert doc.issue_year == 1945
    assert doc.quality_flags == ("missing_scope", "expired_full")
    assert doc.text_status == "available"
    assert doc.legal_unit_count == 5


def test_parse_external_stub_row():
    """Test external stub parsing."""
    row = {
        "id_str": "100",
        "referenced_by_edge_count": "5",
        "quality_flags": ["external_stub"]
    }
    stub = parse_external_stub_row(row)
    assert isinstance(stub, ExternalStubNode)
    assert stub.id_str == "100"
    assert stub.is_external_stub is True
    assert stub.citation_safe is False
    assert stub.referenced_by_edge_count == 5
    assert stub.quality_flags == ("external_stub",)


def test_parse_provision_row():
    """Test provision parsing."""
    row = {
        "unit_id": "1::article::1",
        "id_str": "1",
        "unit_type": "article",
        "article_number": "1",
        "unit_heading": "Điều 1: Phạm vi",
        "path": "article::1",
        "citation_anchor": "Điều 1",
        "char_start": "0",
        "char_end": "100",
        "unit_char_count": "100",
        "unit_token_estimate": "25",
        "chunk_count": "1",
        "coverage_verified": "true"
    }
    prov = parse_provision_row(row)
    assert isinstance(prov, ProvisionNode)
    assert prov.unit_id == "1::article::1"
    assert prov.id_str == "1"
    assert prov.char_start == 0
    assert prov.char_end == 100
    assert prov.coverage_verified is True


def test_parse_chunk_row():
    """Test chunk parsing."""
    row = {
        "chunk_id": "1::article::1::chunk::1",
        "parent_unit_id": "1::article::1",
        "id_str": "1",
        "chunk_index_in_unit": "1",
        "chunk_count_in_unit": "2",
        "unit_split": "1",
        "structuring_quality_flags": []
    }
    chunk = parse_chunk_row(row)
    assert isinstance(chunk, ChunkNode)
    assert chunk.chunk_id == "1::article::1::chunk::1"
    assert chunk.parent_unit_id == "1::article::1"
    assert chunk.chunk_index_in_unit == 1
    assert chunk.unit_split is True
