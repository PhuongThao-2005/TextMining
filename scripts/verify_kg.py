import sys
from pathlib import Path
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in the path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from retrieval.io_utils import read_jsonl
from knowledge_graph import (KnowledgeGraphFacade,
    parse_validity_event_rows,
    parse_authority_index_rows,
    GraphExpansion,
    QueryConstraints,
)

def verify_knowledge_graph():
    print("--------------------------------------------------")
    print("Legal Graph RAG - Knowledge Graph Verification")
    print("--------------------------------------------------")
    
    facade = KnowledgeGraphFacade()
    
    # 1. Load and Build the Knowledge Graph
    print("[1/5] Building Knowledge Graph from data/v2/...")
    start_time = time.time()
    build_result = facade.build_graph()
    duration = time.time() - start_time
    print(f"      Knowledge Graph built in {duration:.2f} seconds.")
    
    # Print build stats
    stats = build_result.stats
    graph = build_result.graph
    print("\n[Build Statistics]")
    print(f"  - Document nodes:      {stats.document_count:,}")
    print(f"  - External Stub nodes: {stats.external_stub_count:,}")
    print(f"  - Provision nodes:     {stats.provision_count:,}")
    print(f"  - Chunk nodes:         {stats.chunk_count:,}")
    print(f"  - Document edges:      {stats.document_edge_count:,}")
    print(f"  - Verified edges:      {stats.verified_document_edge_count:,}")
    print(f"  - Unverified edges:    {stats.unverified_document_edge_count:,}")
    print(f"  - Structural edges:    {stats.structural_edge_count:,}")
    print(f"  - Orphan provisions:   {stats.orphan_provision_count}")
    print(f"  - Orphan chunks:       {stats.orphan_chunk_count}")
    
    # Reconciliation checks
    print("\n[Reconciliation Verification]")
    
    # doc counts matching
    expected_docs = 151624
    if stats.document_count == expected_docs:
        print(f"  [PASS] Document count reconciles exactly: {stats.document_count:,} == {expected_docs:,}")
    else:
        print(f"  [FAIL] Document count discrepancy: {stats.document_count:,} != {expected_docs:,}")
        
    # edge counts matching
    expected_edges = 883256
    if stats.document_edge_count == expected_edges:
        print(f"  [PASS] Edge count reconciles exactly: {stats.document_edge_count:,} == {expected_edges:,}")
    else:
        print(f"  [FAIL] Edge count discrepancy: {stats.document_edge_count:,} != {expected_edges:,}")
        
    # external stubs matching
    expected_stubs = 19763
    if stats.external_stub_count == expected_stubs:
        print(f"  [PASS] External stubs count reconciles exactly: {stats.external_stub_count:,} == {expected_stubs:,}")
    else:
        print(f"  [FAIL] External stubs count discrepancy: {stats.external_stub_count:,} != {expected_stubs:,}")
        
    # citation safety of stubs
    all_stubs_unsafe = all(not stub.citation_safe for stub in graph.external_stubs.values())
    if all_stubs_unsafe:
        print("  [PASS] 100% of ExternalStub nodes are marked citation_safe = False")
    else:
        print("  [FAIL] Some ExternalStub nodes are marked citation_safe = True")
        
    # orphans checking
    if stats.orphan_provision_count == 0 and stats.orphan_chunk_count == 0:
        print("  [PASS] No orphans detected (0 orphan provisions, 0 orphan chunks)")
    else:
        print(f"  [FAIL] Orphans detected! Provisions: {stats.orphan_provision_count}, Chunks: {stats.orphan_chunk_count}")

    # 2. Load Reasoning Overlay
    print("\n[2/5] Loading Reasoning Overlay data...")
    data_dir = PROJECT_ROOT / "data" / "v2"
    validity_events = list(parse_validity_event_rows(read_jsonl(data_dir / "validity_timeline.jsonl")))
    authority_entries = list(parse_authority_index_rows(read_jsonl(data_dir / "authority_index.jsonl")))
    print(f"      Loaded {len(validity_events):,} validity events and {len(authority_entries)} authority index entries.")
    
    # 3. Dynamic Overlay Join
    print("\n[3/5] Computing dynamic overlays for documents...")
    overlay_bundle = facade.build_overlay_bundle(
        documents=graph.documents.values(),
        validity_events=validity_events,
        authority_entries=authority_entries,
        as_of_date="2026-07-13",
    )
    print(f"      Computed overlays for {len(overlay_bundle.document_overlays):,} documents.")
    
    # Spot-check a document's overlay (e.g. Doc ID 72 or a doc that has events)
    doc_with_events = next((o for o in overlay_bundle.document_overlays.values() if o.validity_events), None)
    if doc_with_events:
        print(f"      Spot-check doc ID '{doc_with_events.id_str}':")
        print(f"        - Title: {graph.documents[doc_with_events.id_str].title[:60]}...")
        print(f"        - Resolved Legal Rank: {doc_with_events.legal_authority_rank} (Source: {doc_with_events.authority_rank_source})")
        print(f"        - Computed Currency Status: {doc_with_events.currency_status}")
        print(f"        - Validity Events Count: {len(doc_with_events.validity_events)}")
    else:
        print("      No document found with validity events in this run.")

    # 4. Graph Traversal Test
    print("\n[4/5] Running Graph Traversal Test (mode: basis)...")
    # Find a starting document that has outgoing verified edges
    start_doc_id = None
    for edge in graph.verified_document_edges:
        if edge.src_id in graph.documents and edge.dst_id in graph.documents:
            start_doc_id = edge.src_id
            break
            
    if start_doc_id:
        print(f"      Starting Traversal from Doc ID: '{start_doc_id}'")
        traversal_result = facade.traverse(graph, start_id=start_doc_id, mode="basis", max_depth=3)
        print(f"      Traversal Result:")
        print(f"        - Max Depth: {traversal_result.max_depth}")
        print(f"        - Visited IDs Count: {len(traversal_result.visited_ids)}")
        print(f"        - Visited Edges Count: {len(traversal_result.visited_edges)}")
        print(f"        - Traversal Paths Found: {len(traversal_result.paths)}")
        
        if traversal_result.paths:
            print("      Sample Path:")
            path = traversal_result.paths[0]
            print(f"        Path: {path.start_id} " + " -> ".join(f"[{step.rel_type}]-> {step.dst_id}" for step in path.steps))
            
        # Build Filter test
        print("      Building Whitelist Filter for traversal results...")
        constraints = QueryConstraints(validity_groups=("active", "partial"))
        guided_filter = facade.build_graph_guided_filter(
            graph=graph,
            traversal=traversal_result,
            overlays=overlay_bundle.document_overlays,
            filter_profile="current_law",
            constraints=constraints
        )
        print(f"        - Filter profile: {guided_filter.filter_profile}")
        print(f"        - Whitelisted id_strs count: {len(guided_filter.id_strs)}")
        print(f"        - Empty filter warning? {guided_filter.empty_filter_warning}")
    else:
        print("      Could not find a starting document with verified outgoing edges to test traversal.")

    # 5. Graph Expansion Test
    print("\n[5/5] Running Graph Expansion Test (reading order preservation)...")
    # Find a seed chunk that has a parent provision
    seed_chunk_id = None
    for chunk in graph.chunks.values():
        if chunk.parent_unit_id in graph.provisions:
            seed_chunk_id = chunk.chunk_id
            break
            
    if seed_chunk_id:
        print(f"      Starting expansion from Seed Chunk: '{seed_chunk_id}'")
        expansion_engine = GraphExpansion(graph)
        expansion_result = expansion_engine.expand([seed_chunk_id], max_hop=2, max_context=5)
        print(f"      Expansion Result:")
        print(f"        - Seed Chunks: {expansion_result.seed_chunk_ids}")
        print(f"        - Ordered Context Chunk IDs: {expansion_result.ordered_context_chunks}")
        print(f"        - Traversed Edges Count: {len(expansion_result.traversed_edges)}")
        print(f"        - Warnings: {expansion_result.warnings}")
    else:
        print("      Could not find a seed chunk with parent provision to test expansion.")

    print("\n--------------------------------------------------")
    print("Verification completed successfully.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    verify_knowledge_graph()
