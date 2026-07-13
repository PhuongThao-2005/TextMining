# Knowledge Graph Module Handoff Specification

This handoff details the status, implementation parameters, integration pathways, and immediate checklist items for the next developer working on the G-LRAG v2 Knowledge Graph module.

---

## 1. Current Status

The Knowledge Graph module for v2 has been implemented as an in-memory typed service layer. All 1.5M chunks and 1.3M provisions load and parse correctly under 130 seconds. Path traversals, dynamic currency calculations, and same-provision vector text expansions have been fully verified.

---

## 2. Completed Features

* **Modular Pipeline Service:** Decoupled loaders, parsers, builders, traversals, overlays, and context filters coordinates via a unified facade.
* **Refactored Utilities:** Extracted duplicated private conversion helpers to a shared [utils.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/utils.py).
* **Dynamic Overlay Joining:** publication data, legal rank, and validity timeline indexes are joined dynamically at query time; overlays are never stored on base graph nodes.
* **Gated Traversals:** BFS traversals walk paths over verified edges, successfully excluding unverified edge groups (such as `validity` and `suspension`) from reasoning.
* **Window-Sliding Expansion:** Sibling chunks are extracted in index order, and provision chains are walked forward along `PROVISION_NEXT` to preserve reading order.
* **Integration Whitelists:** Whitelist document ID filters are generated cleanly to restrict vector database scans, surfacing empty sets explicitly.

---

## 3. Missing Features

* **Neo4j Persistence Layer:** Currently, the graph represents an in-memory structure. Materializing these nodes and relationships into a Neo4j database using a Cypher-based persistence adapter remains to be done.
* **Build Report Writer:** Building statistical verification outputs to a physical `graph_build_report.md` file is missing. The statistics are generated in memory (`GraphBuildStats`) but not written to disk.

---

## 4. Architecture and Integration

The graph module sits as a middleware querying planner.

```text
User Query ──▶ GraphTraversal ──▶ ContextBuilder (Overlay Joins)
                                           │
                                           ▼
 VectorStore ◀── VectorRetriever ◀── GraphGuidedFilter (id_str whitelist)
```

The vector search logic in [src/retrieval/retriever.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/retrieval/retriever.py) is kept clean and decoupled from the graph. It expects a whitelisted list of document IDs (`id_str_filter`) from the caller, performing similarity checks only inside the whitelisted set.

---

## 5. Known Issues and Technical Debt

1. **Reverse Edge Direction Naming:**
   - Walking chunk $\rightarrow$ provision registers a traversal step with relation type `PROVISION_HAS_CHUNK` but with the source as chunk, reversing the semantic edge direction.
2. **CP1252 Terminal Crash:**
   - Standard Windows consoles will crash with a `UnicodeEncodeError` when printing Vietnamese characters. We reconfigured `sys.stdout` to UTF-8 in our verification script to fix this.

---

## 6. Assumptions

* **Upstream Structuring:** Assumes provisions are pre-parsed and parent links are clean. No automated repair is done for orphaned records.
* **Verification Flags:** Assumes `direction_verified` is correctly assigned upstream in `edges.jsonl`.
* **Slim Chunk Nodes:** Assumes vector text resides strictly in the vector store and is not loaded into the graph nodes.

---

## 7. Testing

A verification script is available at [scripts/verify_kg.py](file:///d:/HK3_3/Text%20Mining/TextMining/scripts/verify_kg.py). Run it using:
```bash
python scripts/verify_kg.py
```
This script runs the facade to build the graph, load overlays, spot-check overlays, perform path traversals, verify empty whitelist filters, and run same-provision expansions.

---

## 8. Files Modified / Created on Branch `kg`

* **Created:**
  - `src/knowledge_graph/utils.py` (Helper utility functions)
  - `scripts/verify_kg.py` (Verification runner)
  - `docs/README.md` (Index of documents)
  - `docs/GRAPH_MODULE.md` (Module specification)
  - `src/knowledge_graph/README.md` (Quick start and usage examples)
  - `docs/handoff/HANDOFF_GRAPH.md` (This file)
  - `docs/report/FINAL_REPORT.md` (Consolidated integration and audit report)
  - `docs/changelog/` (Changelog entries directory)
  - `pyproject.toml` (Unified python tools config)
* **Modified:**
  - `src/knowledge_graph/parser.py` (Refactored to clean imports and structure)
  - `src/knowledge_graph/edge_parser.py` (Refactored to clean imports and structure)
  - `src/knowledge_graph/overlay.py` (Refactored to fix tie-breaker version sorting and clean imports)

---

## 9. Next Developer Checklist / TODOs

- [ ] **Cypher Persistence Adapter:** Implement a persistence module to write the built graph structures into a Neo4j database instance.
- [ ] **Build Report Writer:** Create a markdown writer class that formats `GraphBuildStats` and warnings, and writes `graph_build_report.md` to disk.
- [x] **Fix Rank Conflict Tie-Breaker:** Refactor version sorting in `overlay.py` to parse trailing integers rather than sorting strings lexicographically.
- [ ] **Standardize Traversal Steps:** Add direction tags (e.g. forward/reverse markers) inside `TraversalStep` to prevent reversed relationship label output.
