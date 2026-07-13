from __future__ import annotations

import pytest

from knowledge_graph import (
    GraphBuilder,
    GraphTraversal,
    DocumentNode,
    GraphEdge,
    FacetValue,
)


@pytest.fixture
def traversal_graph() -> GraphTraversal:
    """Fixture that constructs a simple connected graph for traversal testing."""
    builder = GraphBuilder()
    
    # 4 documents in a line: 1 -> 2 -> 3 -> 4
    docs = [
        DocumentNode(
            id_str=str(i), title=f"Doc {i}", so_ky_hieu=f"{i}", citation_label=f"{i}",
            loai_van_ban="Luật", loai_van_ban_raw="Luật",
            issuing_authority=FacetValue("a", "a", "a"), legal_field=FacetValue("a", "a", "a"),
            sector=FacetValue("a", "a", "a"), scope=FacetValue("a", "a", "a"),
            ngay_ban_hanh_iso="2026-01-01", ngay_co_hieu_luc_iso="2026-01-01", ngay_het_hieu_luc_iso=None,
            issue_year=2026, chuc_danh="a", nguoi_ky="a", quality_flags=(),
        )
        for i in [1, 2, 3, 4, 5] # 5 is disconnected
    ]
    
    edges = [
        # Verified edges
        GraphEdge(
            edge_id="1->2", src_id="1", dst_id="2", rel_canonical="based_on", rel_group="basis", rel_raw="Căn cứ",
            direction_normalized=True, direction_verified=True, external_target=False, edge_quality_flags=(), provenance={},
        ),
        GraphEdge(
            edge_id="2->3", src_id="2", dst_id="3", rel_canonical="based_on", rel_group="basis", rel_raw="Căn cứ",
            direction_normalized=True, direction_verified=True, external_target=False, edge_quality_flags=(), provenance={},
        ),
        GraphEdge(
            edge_id="3->4", src_id="3", dst_id="4", rel_canonical="guides_or_details", rel_group="guidance", rel_raw="Hướng dẫn",
            direction_normalized=True, direction_verified=True, external_target=False, edge_quality_flags=(), provenance={},
        ),
        # Unverified edge
        GraphEdge(
            edge_id="3->5", src_id="3", dst_id="5", rel_canonical="replaces", rel_group="validity", rel_raw="Hết hiệu lực",
            direction_normalized=True, direction_verified=False, external_target=False, edge_quality_flags=(), provenance={},
        ),
        # Circular loop (verified) back from 4 to 1
        GraphEdge(
            edge_id="4->1", src_id="4", dst_id="1", rel_canonical="based_on", rel_group="basis", rel_raw="Căn cứ",
            direction_normalized=True, direction_verified=True, external_target=False, edge_quality_flags=(), provenance={},
        ),
    ]
    
    graph = builder.build(documents=docs, external_stubs=[], provisions=[], chunks=[], edges=edges).graph
    return GraphTraversal(graph)


def test_traversal_basis_depth_and_loops(traversal_graph):
    """Test that traverse_basis respects depth caps and avoids infinite loop on circular edges."""
    
    # Traverse from 1, depth 1
    res1 = traversal_graph.traverse_basis(start_id="1", max_depth=1)
    assert set(res1.visited_ids) == {"1", "2"}
    assert len(res1.paths) == 1
    
    # Traverse from 1, depth 3
    res3 = traversal_graph.traverse_basis(start_id="1", max_depth=3)
    # paths: 1 -> 2 (depth 1), 1 -> 2 -> 3 (depth 2), 3 -> 4 is GUIDANCE (not basis), so it stops at 3.
    # 4 -> 1 loop is not visited because 3 is not linked to 4 via basis.
    assert set(res3.visited_ids) == {"1", "2", "3"}
    assert len(res3.paths) == 2


def test_traversal_direction_verified_filtering(traversal_graph):
    """Test that traversal excludes unverified edges from visited candidates."""
    
    # Traverse neighbors from 3.
    # Outgoing verified edges from 3: 3 -> 4 (guidance)
    # Outgoing unverified edges from 3: 3 -> 5 (validity, direction_verified = False)
    res = traversal_graph.traverse_neighbors(start_id="3", max_depth=1)
    
    # Doc 4 is visited, Doc 5 is EXCLUDED because 3->5 is unverified.
    assert "4" in res.visited_ids
    assert "5" not in res.visited_ids


def test_traversal_disconnected_graph(traversal_graph):
    """Test traversal starting from a disconnected node."""
    res = traversal_graph.traverse(start_id="5", mode="basis", max_depth=3)
    assert res.visited_ids == ("5",)
    assert len(res.paths) == 0
