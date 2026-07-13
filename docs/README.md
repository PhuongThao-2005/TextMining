# G-LRAG Knowledge Graph Module

This module implements the Knowledge Graph middleware for the G-LRAG v2 pipeline. It structures documents, provisions, and chunks in-memory, maps their structural and sequencing relationships, traverses them via Breadth-First Search (BFS), and dynamically overlays validity timeline and authority indexes at query time.

---

## 1. Quick Start

### 1.1 Prerequisites
Ensure that the v2 dataset files are compiled and located under `data/v2/`:
- `documents.jsonl`, `external_stubs.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`
- `validity_timeline.jsonl`, `authority_index.jsonl`, `text_provenance.jsonl`

### 1.2 Verification
To run the verification checks and tests, execute:
```bash
# Run the complete test suite
pytest tests/knowledge_graph -v

# Run the end-to-end integration script
python scripts/verify_kg.py
```

---

## 2. Folder Structure

```text
src/knowledge_graph/
├── __init__.py           # Exports public facades, schemas, and helpers
├── builder.py            # Materializes structural links and reading order
├── context.py            # Computes GraphGuidedFilter whitelist candidates
├── context_schema.py     # Value types for whitelists and filters
├── edge_parser.py        # Edge normalization and verification gating
├── edge_schema.py        # GraphEdge structure
├── expansion.py          # Horizontally expands seed chunks in reading order
├── expansion_schema.py   # Value types for expansion results and steps
├── facade.py             # Public unified coordination boundary
├── loader.py             # File stream loader
├── overlay.py            # dynamic validity timeline folder and rank resolver
├── overlay_schema.py     # Value types for overlays and timeline events
├── parser.py             # Node parsers and provenance joiner
├── schema.py             # Core node models (Document, Provision, Chunk, Stub)
└── utils.py              # Consolidated string, boolean, and flag helpers
```

---

## 3. Documentation Index

* **[GRAPH_MODULE.md](file:///d:/HK3_3/Text%20Mining/TextMining/docs/GRAPH_MODULE.md)**
  - *Purpose:* Primary module specification detailing objectives, system architecture, package structure, and data model.
* **[handoff/HANDOFF_GRAPH.md](file:///d:/HK3_3/Text%20Mining/TextMining/docs/handoff/HANDOFF_GRAPH.md)**
  - *Purpose:* Developer handoff checklist, detailing current in-memory status, completed features, known integration points, and checklist items.
* **[report/FINAL_REPORT.md](file:///d:/HK3_3/Text%20Mining/TextMining/docs/report/FINAL_REPORT.md)**
  - *Purpose:* Consolidated final audit, combining implementation summaries, runtime test metrics, and compliance score analysis.
* **[changelog/](file:///d:/HK3_3/Text%20Mining/TextMining/docs/changelog/)**
  - *Purpose:* Chronological list of logical changes introduced in the `kg` branch (loaders, builders, expansion, overlays, and refactoring).
