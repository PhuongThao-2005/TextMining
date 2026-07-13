# Changelog — Graph Traversal & Expansion

## Summary
Implemented the `GraphTraversal` path reasoning engine and the `GraphExpansion` localized context expansion module to support same-provision context window sliding and multi-hop legal searches.

## Motivation
Retrieved vector chunks are often isolated fragments of code. To build comprehensive context for legal QA, retrieval planners must walk multi-hop legal bases and expand vector hits into cohesive, reading-order preserved text.

## Files Changed
* **Created:**
  - `src/knowledge_graph/traversal.py` (BFS path reasoning engine)
  - `src/knowledge_graph/expansion.py` (Same-provision sliding window context expansion)
  - `src/knowledge_graph/expansion_schema.py` (Value types for expansion results and steps)

## Major Implementation Details
* **GraphTraversal:** 
  - Implements Breadth-First Search (BFS) pathfinding.
  - Supports traversal modes: `basis` (capped at depth 3), `guidance` ( Decree/Circular links), `validity` (lineage), and `structure` (internal hierarchy).
  - Traversal adjacency is strictly gated on verified document edges (`direction_verified == True`).
* **GraphExpansion:**
  - Slices sibling chunks under parent provisions sorted by `chunk_index_in_unit`.
  - Slides sliding window context containing adjacent sibling chunks connected via `CHUNK_NEXT`.
  - Chains subsequent provisions along `PROVISION_NEXT` to preserve original legal reading order across hop budgets.

## Breaking Changes
None.

## Migration Notes
None.
