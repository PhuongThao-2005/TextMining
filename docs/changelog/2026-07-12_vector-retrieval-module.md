# 2026-07-12 - Vector Retrieval Module

## Added

- Implemented `src/retrieval/` as a scoped vector retrieval module for v2 data:
  - join-based `retrieval_text` construction from `chunks -> provisions -> documents`;
  - payload construction with citation metadata, authority/validity fields, and facet `_code`/`_surface` fields;
  - sentence-transformers production embedder and deterministic hashing embedder for smoke tests;
  - Qdrant vector store adapter and in-memory vector store for tests/dev;
  - vector indexer that streams chunks, validates duplicates/join misses, writes `vector_index_report.md`;
  - baseline retriever with `current_law`, `broad`, `historical`, and `graph_guided` filter profiles, same-provision expansion, citation-ready results, and reranking signals.
- Added `scripts/build_vector_index.py` CLI for Qdrant production indexing or local smoke indexing.
- Added unit tests covering retrieval text template, current-law filtering, graph-guided empty-filter handling, historical retrieval, same-provision expansion, and citation output.

## Notes

- The code auto-prefers `data/v2/` when present and falls back to the workspace's current `data/pre-processed/` layout.
- Production embedding requires installing `sentence-transformers` and running Qdrant; local tests do not require either dependency.
