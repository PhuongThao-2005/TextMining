# Changelog — Graph Builder

## Summary
Introduced the `GraphBuilder` class to assemble typed G-LRAG v2 records into an in-memory graph structure. It materializes containment links and sequences sequential sibling provisions/chunks to maintain document reading order.

## Motivation
The knowledge graph must represent not only document relationships but also the hierarchical structure of laws (Document $\rightarrow$ Provision $\rightarrow$ Chunk) and chronological sequencing. This allows planners to reconstruct full articles and walk between adjacent clauses.

## Files Changed
* **Created:**
  - `src/knowledge_graph/builder.py` (GraphBuilder, KnowledgeGraph, GraphBuildStats, GraphBuildResult, StructuralEdge)

## Major Implementation Details
* **Structural Containment:** Maps documents to provisions using `DOCUMENT_HAS_PROVISION` edges and provisions to chunks via `PROVISION_HAS_CHUNK` edges.
* **Materialized Reading Order:**
  - Sequences provisions inside a document chronologically using `PROVISION_NEXT` based on `char_start`.
  - Sequences chunks inside a provision chronologically using `CHUNK_NEXT` based on `chunk_index_in_unit`.
* **Constraint Gating:** Asserts uniqueness constraints for document, provision, and chunk identifiers, throwing `ValueError` on duplicates.
* **Orphan Reporting:** Calculates orphan counts and missing target statistics during construction, returning them in `GraphBuildStats`.

## Breaking Changes
None.

## Migration Notes
The builder operates strictly in-memory. Neo4j database persistence will be implemented in the next milestone.
