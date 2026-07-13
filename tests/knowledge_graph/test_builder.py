from __future__ import annotations

import pytest

from knowledge_graph import (
    GraphBuilder,
    KnowledgeGraph,
    DocumentNode,
    ProvisionNode,
    ChunkNode,
    FacetValue,
)


def test_graph_builder_builds_successfully(
    mock_document_node,
    mock_external_stub_node,
    mock_provision_node,
    mock_chunk_node,
    mock_graph_edge,
):
    """Test that GraphBuilder builds all nodes and edges correctly and maps containment."""
    builder = GraphBuilder()
    
    # Run build
    build_result = builder.build(
        documents=[mock_document_node],
        external_stubs=[mock_external_stub_node],
        provisions=[mock_provision_node],
        chunks=[mock_chunk_node],
        edges=[mock_graph_edge],
    )
    
    graph = build_result.graph
    stats = build_result.stats
    
    assert isinstance(graph, KnowledgeGraph)
    
    # Check node sizes
    assert len(graph.documents) == 1
    assert len(graph.external_stubs) == 1
    assert len(graph.provisions) == 1
    assert len(graph.chunks) == 1
    assert len(graph.document_edges) == 1
    
    # Check containment edges
    assert len(graph.structural_edges) == 2  # HAS_PROVISION + HAS_CHUNK (next edges are empty since count is 1)
    assert graph.document_to_provisions["1"] == ("1::article::1",)
    assert graph.provision_to_chunks["1::article::1"] == ("1::article::1::chunk::1",)
    
    # Check stats
    assert stats.document_count == 1
    assert stats.orphan_provision_count == 0
    assert stats.orphan_chunk_count == 0


def test_graph_builder_rejects_duplicate_nodes(mock_document_node):
    """Test that GraphBuilder raises ValueError on duplicate node identifiers."""
    builder = GraphBuilder()
    
    # Duplicate documents with same id_str
    with pytest.raises(ValueError) as exc_info:
        builder.build(
            documents=[mock_document_node, mock_document_node],
            external_stubs=[],
            provisions=[],
            chunks=[],
            edges=[],
        )
    assert "Duplicate graph identifiers for id_str" in str(exc_info.value)


def test_graph_builder_detects_orphans(mock_provision_node, mock_chunk_node):
    """Test that GraphBuilder counts and flags orphaned provisions and chunks."""
    builder = GraphBuilder()
    
    # 1. Build with provisions and chunks but NO documents
    build_result = builder.build(
        documents=[],
        external_stubs=[],
        provisions=[mock_provision_node],
        chunks=[mock_chunk_node],
        edges=[],
    )
    
    stats = build_result.stats
    assert len(build_result.warnings) == 1
    assert build_result.warnings[0] == mock_provision_node.unit_id
    
    assert stats.orphan_provision_count == 1
    assert stats.orphan_chunk_count == 0  # chunk has a valid parent provision
    
    # 2. Build with chunks but NO provisions or documents
    build_result_no_prov = builder.build(
        documents=[],
        external_stubs=[],
        provisions=[],
        chunks=[mock_chunk_node],
        edges=[],
    )
    assert build_result_no_prov.stats.orphan_chunk_count == 1



def test_graph_builder_materializes_reading_order():
    """Test that GraphBuilder materializes CHUNK_NEXT and PROVISION_NEXT edges correctly."""
    builder = GraphBuilder()
    
    doc = DocumentNode(
        id_str="1", title="D1", so_ky_hieu="1", citation_label="1",
        loai_van_ban="Luật", loai_van_ban_raw="Luật",
        issuing_authority=FacetValue("a", "a", "a"), legal_field=FacetValue("a", "a", "a"),
        sector=FacetValue("a", "a", "a"), scope=FacetValue("a", "a", "a"),
        ngay_ban_hanh_iso="2026-01-01", ngay_co_hieu_luc_iso="2026-01-01", ngay_het_hieu_luc_iso=None,
        issue_year=2026, chuc_danh="a", nguoi_ky="a", quality_flags=(),
    )
    
    # Sibling provisions (different offsets)
    prov1 = ProvisionNode(
        unit_id="1::article::1", id_str="1", unit_type="article", article_number="1",
        unit_heading="H1", path="p1", citation_anchor="c1",
        char_start=0, char_end=50, unit_char_count=50, unit_token_estimate=12,
        chunk_count=1, coverage_verified=True,
    )
    prov2 = ProvisionNode(
        unit_id="1::article::2", id_str="1", unit_type="article", article_number="2",
        unit_heading="H2", path="p2", citation_anchor="c2",
        char_start=51, char_end=100, unit_char_count=49, unit_token_estimate=12,
        chunk_count=1, coverage_verified=True,
    )
    
    # Sibling chunks under provision 1
    chunk1 = ChunkNode(
        chunk_id="1::article::1::chunk::1", parent_unit_id="1::article::1", id_str="1",
        chunk_index_in_unit=1, chunk_count_in_unit=2, unit_split=True, structuring_quality_flags=(),
    )
    chunk2 = ChunkNode(
        chunk_id="1::article::1::chunk::2", parent_unit_id="1::article::1", id_str="1",
        chunk_index_in_unit=2, chunk_count_in_unit=2, unit_split=True, structuring_quality_flags=(),
    )
    
    build_result = builder.build(
        documents=[doc],
        external_stubs=[],
        provisions=[prov1, prov2],
        chunks=[chunk1, chunk2],
        edges=[],
    )
    
    graph = build_result.graph
    
    # Verify adjacent pointers exist
    assert graph.provision_next["1::article::1"] == "1::article::2"
    assert "1::article::2" not in graph.provision_next
    
    assert graph.chunk_next["1::article::1::chunk::1"] == "1::article::1::chunk::2"
    assert "1::article::1::chunk::2" not in graph.chunk_next
