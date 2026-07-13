from __future__ import annotations

from pathlib import Path


from knowledge_graph import (
    KnowledgeGraphFacade,
    GraphLoaderPaths,
    OverlayBundle,
    ValidityEvent,
    AuthorityIndexEntry,
)


def test_facade_full_integration_pipeline(mock_dataset_dir: Path):
    """Test the full load -> build -> traverse -> overlay -> context facade integration pipeline."""
    
    # Initialize facade with custom directory paths
    paths = GraphLoaderPaths(data_dir=mock_dataset_dir)
    facade = KnowledgeGraphFacade(paths=paths)
    
    # 1. Load and Build structural graph
    build_result = facade.build_graph()
    graph = build_result.graph
    stats = build_result.stats
    
    assert stats.document_count == 2
    assert stats.provision_count == 3
    assert stats.chunk_count == 3
    assert stats.orphan_provision_count == 0
    assert stats.orphan_chunk_count == 0
    
    # 2. Dynamic Overlay joining
    # Build overlay data manually simulating client files loading
    events = [
        ValidityEvent("1", "enacted", "2026-01-01", "0", "whole", "based_on", "e1", True),
        ValidityEvent("2", "enacted", "2026-03-01", "0", "whole", "based_on", "e2", True),
    ]
    entries = [
        AuthorityIndexEntry("Luật", 2, "Law", "authority@1"),
        AuthorityIndexEntry("Nghị định", 4, "Decree", "authority@1"),
    ]
    
    overlay_bundle = facade.build_overlay_bundle(
        documents=graph.documents.values(),
        validity_events=events,
        authority_entries=entries,
        as_of_date="2026-07-13",
    )
    
    assert isinstance(overlay_bundle, OverlayBundle)
    assert len(overlay_bundle.document_overlays) == 2
    assert overlay_bundle.document_overlays["1"].currency_status == "active"
    assert overlay_bundle.document_overlays["1"].legal_authority_rank == 2
    
    traversal = facade.traverse(graph, start_id="2", mode="guidance", max_depth=3)
    assert set(traversal.visited_ids) == {"2", "1"}
    assert len(traversal.paths) == 1

    
    # 4. Context Filtering
    guided_filter = facade.build_graph_guided_filter(
        graph=graph,
        traversal=traversal,
        overlays=overlay_bundle.document_overlays,
        filter_profile="current_law",
    )
    # Both Doc 1 and 2 are active (active / active), so both are whitelisted
    assert set(guided_filter.id_strs) == {"1", "2"}
    assert guided_filter.empty_filter_warning is False
    
    # 5. Local Context Expansion
    # Sibling chunks for provision 1::article::1
    # Seed: '1::article::1::chunk::1'
    # Sibling under same provision: none in mock dataset (it's 1 chunk per unit),
    # but walking PROVISION_NEXT gets provision 1::article::2 which has '1::article::2::chunk::1'.
    expansion_res = facade.context_builder.build_evidence_context(
        graph=graph,
        traversal=traversal,
        overlays=overlay_bundle.document_overlays,
        filter_profile="current_law",
    )
    assert set(expansion_res.documents) == {"1", "2"}
    assert len(expansion_res.overlays) == 2
    assert not expansion_res.warnings
