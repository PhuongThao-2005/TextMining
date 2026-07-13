from __future__ import annotations

import pytest

from knowledge_graph import (
    ContextBuilder,
    QueryConstraints,
    TraversalResult,
    DocumentOverlay,
    GraphBuilder,
    DocumentNode,
    FacetValue,
)


@pytest.fixture
def context_inputs() -> tuple[GraphBuilder, dict[str, DocumentOverlay], TraversalResult]:
    """Fixture that returns structured graph assets for context building tests."""
    builder = GraphBuilder()
    docs = [
        DocumentNode(
            id_str="1", title="D1", so_ky_hieu="1", citation_label="1",
            loai_van_ban="Luật", loai_van_ban_raw="Luật",
            issuing_authority=FacetValue("QH", "QH", "QH"), legal_field=FacetValue("ADMIN", "ADMIN", "ADMIN"),
            sector=FacetValue("s", "s", "s"), scope=FacetValue("sc", "sc", "sc"),
            ngay_ban_hanh_iso="2026-01-01", ngay_co_hieu_luc_iso="2026-01-01", ngay_het_hieu_luc_iso=None,
            issue_year=2026, chuc_danh="a", nguoi_ky="a", quality_flags=(),
        ),
        DocumentNode(
            id_str="2", title="D2", so_ky_hieu="2", citation_label="2",
            loai_van_ban="Luật", loai_van_ban_raw="Luật",
            issuing_authority=FacetValue("QH", "QH", "QH"), legal_field=FacetValue("CIVIL", "CIVIL", "CIVIL"),
            sector=FacetValue("s", "s", "s"), scope=FacetValue("sc", "sc", "sc"),
            ngay_ban_hanh_iso="2026-01-01", ngay_co_hieu_luc_iso="2026-01-01", ngay_het_hieu_luc_iso=None,
            issue_year=2024, chuc_danh="a", nguoi_ky="a", quality_flags=(),
        )
    ]
    graph = builder.build(documents=docs, external_stubs=[], provisions=[], chunks=[], edges=[]).graph
    
    overlays = {
        "1": DocumentOverlay("1", "active", "2026-07-13", 2, "src"),
        "2": DocumentOverlay("2", "expired", "2026-07-13", 2, "src"),
    }
    
    traversal = TraversalResult(
        start_id="1", mode="basis", max_depth=3,
        visited_ids=("1", "2"), visited_edges=(), paths=()
    )
    
    return graph, overlays, traversal


def test_context_builder_guided_filter_profiles(context_inputs):
    """Test candidate document filtering across profiles (current_law vs broad)."""
    graph, overlays, traversal = context_inputs
    cb = ContextBuilder()
    
    # 1. Profile: current_law (ignores expired Doc 2)
    f_current = cb.build_graph_guided_filter(
        graph=graph, traversal=traversal, overlays=overlays, filter_profile="current_law"
    )
    assert f_current.id_strs == ("1",)
    assert f_current.empty_filter_warning is False
    
    # 2. Profile: broad (includes expired Doc 2)
    f_broad = cb.build_graph_guided_filter(
        graph=graph, traversal=traversal, overlays=overlays, filter_profile="broad"
    )
    assert set(f_broad.id_strs) == {"1", "2"}


def test_context_builder_applies_constraints(context_inputs):
    """Test that ContextBuilder filters candidate whitelists using metadata constraints."""
    graph, overlays, traversal = context_inputs
    cb = ContextBuilder()
    
    # Filter with constraint: issue_year_min = 2025 (excludes Doc 2 which is 2024)
    constraints = QueryConstraints(issue_year_min=2025)
    f_constrained = cb.build_graph_guided_filter(
        graph=graph, traversal=traversal, overlays=overlays,
        filter_profile="broad", constraints=constraints
    )
    assert f_constrained.id_strs == ("1",)
    
    # Filter with constraint: legal_field_codes = ('ADMIN',) (excludes Doc 2 which is 'CIVIL')
    constraints_field = QueryConstraints(legal_field_codes=("ADMIN",))
    f_field = cb.build_graph_guided_filter(
        graph=graph, traversal=traversal, overlays=overlays,
        filter_profile="broad", constraints=constraints_field
    )
    assert f_field.id_strs == ("1",)


def test_context_builder_surfaces_empty_filters(context_inputs):
    """Test that ContextBuilder returns explicit warnings on empty whitelists."""
    graph, overlays, traversal = context_inputs
    cb = ContextBuilder()
    
    # Constraint matches nothing: issue_year_min = 2030
    constraints = QueryConstraints(issue_year_min=2030)
    res = cb.build_graph_guided_filter(
        graph=graph, traversal=traversal, overlays=overlays,
        filter_profile="broad", constraints=constraints
    )
    
    assert len(res.id_strs) == 0
    assert res.empty_filter_warning is True
    assert "No documents matched" in res.reason
