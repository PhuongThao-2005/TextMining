from __future__ import annotations

from knowledge_graph import (
    OverlayJoiner,
    ValidityEvent,
    AuthorityIndexEntry,
)


def test_compute_currency_status():
    """Test dynamic folding of chronological validity events."""
    from knowledge_graph.overlay import compute_currency_status
    
    events = [
        ValidityEvent("1", "enacted", "2026-01-01", "0", "whole", "based_on", "e1", True),
        # Unverified event (should be ignored)
        ValidityEvent("1", "expired", "2026-06-01", "2", "whole", "replaces", "e2", False),
        # Verified amendment
        ValidityEvent("1", "amended", "2026-07-01", "3", "part", "amends", "e3", True),
    ]
    
    # Folding up to '2026-05-01' (only enacted event is effective)
    status_may = compute_currency_status("1", events, as_of_date="2026-05-01")
    assert status_may == "active"
    
    # Folding up to '2026-07-15'
    # Expired event (2026-06-01) is ignored because direction_verified is False.
    # Amended event (2026-07-01) is applied because direction_verified is True.
    status_july = compute_currency_status("1", events, as_of_date="2026-07-15")
    assert status_july == "partial"


def test_resolve_authority_rank_conflicts():
    """Test precedence rules for resolving multiple matching document type ranks."""
    from knowledge_graph.overlay import resolve_authority_rank_conflicts
    
    candidates = [
        # Rank 2, version 1
        AuthorityIndexEntry("Luật", 2, "Law", "authority@1"),
        # Rank 2, version 2 (newer)
        AuthorityIndexEntry("Luật", 2, "Law", "authority@2"),
        # Rank 3, version 3 (lower precedence rank integer)
        AuthorityIndexEntry("Luật", 3, "Law", "authority@3"),
    ]
    
    # Conflict resolution chooses lowest rank integer (2), then newest version (authority@2)
    best = resolve_authority_rank_conflicts("Luật", candidates)
    assert best.legal_authority_rank == 2
    assert best.version == "authority@2"


def test_overlay_joiner_handles_missing_entries(mock_document_node):
    """Test OverlayJoiner join outputs with missing events/ranks."""
    joiner = OverlayJoiner()
    
    # Build with empty overlay entries
    bundle = joiner.build_bundle(
        documents=[mock_document_node],
        validity_events=[],
        authority_entries=[],
    )
    
    overlay = bundle.document_overlays["1"]
    assert overlay.id_str == "1"
    assert overlay.currency_status == "unknown" # default when no events
    assert overlay.legal_authority_rank == 99 # fallback rank
    assert overlay.authority_rank_source == "fallback"
