# Changelog — Graph Loader & Parsers

## Summary
Introduced the `GraphLoader` and record parsing layer to load and structure the v2 G-LRAG dataset. It parses raw line-by-line JSONL streams into typed dataclass nodes (`DocumentNode`, `ExternalStubNode`, `ProvisionNode`, `ChunkNode`) and edge structures (`GraphEdge`), handling normalization, text cleanups, and nested facets.

## Motivation
To bootstrap the Knowledge Graph module, we need a robust, referentially safe ingestion layer that reads the G-LRAG v2 dataset files dynamically. Static analysis tools and runtime runners need clean mappings that decouple file scanning from graph database mutations.

## Files Changed
* **Created:**
  - `src/knowledge_graph/loader.py` (File gateway and GraphLoaderPaths/GraphLoader)
  - `src/knowledge_graph/parser.py` (Enriches documents with text provenance and translates records)
  - `src/knowledge_graph/edge_parser.py` (Processes edge directions and filters verified relationships)
  - `src/knowledge_graph/schema.py` (Core node dataclass definitions)
  - `src/knowledge_graph/edge_schema.py` (GraphEdge structure definition)
  - `src/knowledge_graph/utils.py` (Consolidated type conversion and quality flag normalizers)

## Major Implementation Details
* **GraphLoader:** Exposes stream loading for each G-LRAG v2 JSONL file. Rejects directory configurations missing any required file to protect pipeline referential integrity.
* **Parser:** Normalizes facets to `{code, surface, raw}` triples. Resolves null properties to `"MISSING"` / `"UNMAPPED"`.
* **Edge Parser:** Normalizes relationship edges to active-voice directed records. Filters verified-only edges (`direction_verified == True`) for traversal usage.
* **Schema definitions:** `ChunkNode` is structured to only store keys and index pointers, excluding chunk text to save memory. `ExternalStubNode` enforces `citation_safe = False`.

## Breaking Changes
None (new module).

## Migration Notes
Ensure that the upstream dataset is compiled and located under `data/v2/`.
