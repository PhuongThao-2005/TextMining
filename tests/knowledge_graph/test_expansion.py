from __future__ import annotations

import pytest

from knowledge_graph import (
    GraphBuilder,
    GraphExpansion,
    DocumentNode,
    ProvisionNode,
    ChunkNode,
    FacetValue,
)


@pytest.fixture
def expansion_graph() -> GraphExpansion:
    """Fixture that builds a document structural tree for expansion testing."""
    builder = GraphBuilder()
    
    doc = DocumentNode(
        id_str="1", title="D1", so_ky_hieu="1", citation_label="1",
        loai_van_ban="Luật", loai_van_ban_raw="Luật",
        issuing_authority=FacetValue("a", "a", "a"), legal_field=FacetValue("a", "a", "a"),
        sector=FacetValue("a", "a", "a"), scope=FacetValue("a", "a", "a"),
        ngay_ban_hanh_iso="2026-01-01", ngay_co_hieu_luc_iso="2026-01-01", ngay_het_hieu_luc_iso=None,
        issue_year=2026, chuc_danh="a", nguoi_ky="a", quality_flags=(),
    )
    
    # 2 sibling provisions: article 1 and article 2
    prov1 = ProvisionNode(
        unit_id="1::article::1", id_str="1", unit_type="article", article_number="1",
        unit_heading="H1", path="p1", citation_anchor="c1",
        char_start=0, char_end=100, unit_char_count=100, unit_token_estimate=25,
        chunk_count=2, coverage_verified=True,
    )
    prov2 = ProvisionNode(
        unit_id="1::article::2", id_str="1", unit_type="article", article_number="2",
        unit_heading="H2", path="p2", citation_anchor="c2",
        char_start=101, char_end=200, unit_char_count=99, unit_token_estimate=25,
        chunk_count=2, coverage_verified=True,
    )
    
    # Chunks for provision 1 (index 1 & 2)
    chunk1_1 = ChunkNode(
        chunk_id="1::article::1::chunk::1", parent_unit_id="1::article::1", id_str="1",
        chunk_index_in_unit=1, chunk_count_in_unit=2, unit_split=True, structuring_quality_flags=(),
    )
    chunk1_2 = ChunkNode(
        chunk_id="1::article::1::chunk::2", parent_unit_id="1::article::1", id_str="1",
        chunk_index_in_unit=2, chunk_count_in_unit=2, unit_split=True, structuring_quality_flags=(),
    )
    
    # Chunks for provision 2 (index 1 & 2)
    chunk2_1 = ChunkNode(
        chunk_id="1::article::2::chunk::1", parent_unit_id="1::article::2", id_str="1",
        chunk_index_in_unit=1, chunk_count_in_unit=2, unit_split=True, structuring_quality_flags=(),
    )
    chunk2_2 = ChunkNode(
        chunk_id="1::article::2::chunk::2", parent_unit_id="1::article::2", id_str="1",
        chunk_index_in_unit=2, chunk_count_in_unit=2, unit_split=True, structuring_quality_flags=(),
    )
    
    graph = builder.build(
        documents=[doc],
        external_stubs=[],
        provisions=[prov1, prov2],
        chunks=[chunk1_1, chunk1_2, chunk2_1, chunk2_2],
        edges=[],
    ).graph
    return GraphExpansion(graph)


def test_expansion_respects_max_context(expansion_graph):
    """Test same-provision context window limits."""
    # Seed: chunk 1_1. Limit: max_context = 1.
    res = expansion_graph.expand(["1::article::1::chunk::1"], max_hop=1, max_context=1)
    
    # Window centers on 1_1, resulting in only 1_1
    assert res.ordered_context_chunks == ("1::article::1::chunk::1",)


def test_expansion_preserves_reading_order_and_hop(expansion_graph):
    """Test expansion across PROVISION_NEXT hops while preserving natural reading order."""
    # Seed: chunk 1_2. Hops: 2 (gets prov1 + next prov2). Context: 3.
    res = expansion_graph.expand(["1::article::1::chunk::2"], max_hop=2, max_context=3)
    
    # Prov1 chunks sorted: [1_1, 1_2]. Sibling window for 1_2 (context limit 3): centers on 1_2, gets [1_1, 1_2].
    # Follows PROVISION_NEXT to Prov2. Chunks sorted: [2_1, 2_2].
    # Cumulative: [1_1, 1_2, 2_1, 2_2] -> capped to max_context=3.
    # Expected reading order: 1_1, 1_2, 2_1
    assert res.ordered_context_chunks == (
        "1::article::1::chunk::1",
        "1::article::1::chunk::2",
        "1::article::2::chunk::1",
    )
    
    # Verify traversed structural edges contain CHUNK_NEXT and PROVISION_NEXT steps
    types = [step.rel_type for step in res.traversed_edges]
    assert "CHUNK_NEXT" in types
    assert "PROVISION_NEXT" in types
    assert "PROVISION_HAS_CHUNK" in types
