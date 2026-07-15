# Quickstart: Notebook Graph Module Integration

Validation guide for running [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) after hybrid graph integration. This is **not** the implementation itself — see [`plan.md`](plan.md), [`data-model.md`](data-model.md), and [`research.md`](research.md). Task breakdown belongs in `tasks.md` (via `/speckit-tasks`).

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.11+ Jupyter kernel | Same env as `src/` |
| Packages | `faiss-cpu`, `sentence-transformers`, `pandas`, `openai` (already listed in notebook install cell) |
| FAISS artifacts | `data/faiss_index/index.faiss`, `payloads.jsonl` (+ optional cache/id_map) |
| Graph structural sources | `data/v2/documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`, `external_stubs.jsonl` |
| Overlay sources (optional) | `data/v2/validity_timeline.jsonl`, `authority_index.jsonl` |
| Generator credentials (optional) | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME` |
| Working directory | Project root **or** `notebooks/` (root resolution automatic, FR-016) |

### Expected inputs (preflight)

```text
data/faiss_index/
  index.faiss
  payloads.jsonl
  id_map.json              # optional
  payload_cache.sqlite     # optional / auto-built

data/v2/
  documents.jsonl          # required for graph
  provisions.jsonl         # required for graph
  chunks.jsonl             # required for graph
  edges.jsonl              # required for graph
  external_stubs.jsonl     # required for graph
  validity_timeline.jsonl  # optional overlays
  authority_index.jsonl    # optional overlays
```

If structural graph files are missing, the notebook must list them and keep pure vector retrieval usable. If only overlays are missing, structural hybrid expansion remains available with an explicit overlays-unavailable label.

## Setup (once)

From project root:

```bash
# Optional dependency smoke check
python -c "import faiss, sentence_transformers, pandas; print('ok')"

# Existing graph module tests still pass (no required new tests for this feature)
python -m pytest tests/knowledge_graph -q
```

Optional generator env:

```bash
export LLM_BASE_URL="https://api.example.com/v1"
export LLM_API_KEY="sk-..."
export LLM_MODEL_NAME="your-model-name"
```

Open [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) with the project kernel.

## Config cell (near top)

| Parameter | Suggested default | Purpose |
| --- | --- | --- |
| `INDEX_DIR` | `{root}/data/faiss_index` | FAISS artifacts |
| `V2_DATA_DIR` | `{root}/data/v2` | Graph + overlay sources |
| `TOP_K` / `TOP_N` / `SCORE_THRESHOLD` | existing notebook defaults | Vector retrieval |
| `DEFAULT_FILTER_PROFILE` | `broad` or `current_law` | Non-graph vector profile |
| `ENABLE_HYBRID_EXPANSION` | `True` | Primary hybrid path switch |
| `HYBRID_MAX_HOP` | `1` or `2` | Graph expansion hop budget |
| `HYBRID_MAX_CONTEXT` | e.g. `12` | Cap ordered expanded chunks |
| `AS_OF_DATE` | e.g. `2026-07-13` | Overlay join date |
| `USE_HYBRID_EVIDENCE_FOR_GENERATION` | `True` | `ask()` feeds expanded evidence |
| `LOCAL_EXPAND_UNITS` | `False` for hybrid demos | Avoid conflating local vs graph expansion |
| `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO` | `False` | Secondary whitelist-before-search demo |

## Recommended run order

1. **Environment + path** — `src/` on `sys.path`, resolve project root.
2. **Config** — parameters above, including hybrid flags (FR-021).
3. **FAISS preflight + load** — existing vector store / retriever setup.
4. **Graph preflight** — list present/missing structural + overlay files (FR-003).
5. **Graph build** — `KnowledgeGraphFacade` → `build_graph()` → print stats (FR-004).
6. **Overlay join** — if files present, `build_overlay_bundle(as_of_date=AS_OF_DATE)` + coverage (FR-005).
7. **Wire expansion** — `GraphExpansion(graph)` into hybrid helpers / `VectorRetriever`.
8. **Seed vector query** — show seed hits with identities.
9. **Hybrid expand** — expand seeds, show seed vs expanded diagnostics + warnings (FR-006/FR-007/FR-018).
10. **Overlay diagnostics** — currency/authority for involved documents when available (FR-008).
11. **Vector-only vs hybrid comparison** — same query, labeled counts/deltas (FR-011).
12. **Optional graph-guided pre-filter demo** — whitelist size + empty-filter warning (FR-020).
13. **`ask()` full pipeline** — hybrid evidence → generation when configured (FR-009/FR-022); retrieval-only if no credentials (US1.4).

## Validation scenarios

### V1 — Happy path hybrid pipeline (US1, SC-001/SC-002/SC-003)

**Given** FAISS artifacts + structural graph sources present.

**When** setup cells and one sample query run with `ENABLE_HYBRID_EXPANSION=True`.

**Then**:
- no unhandled exception
- seed vector hits are shown
- graph expansion diagnostics are shown (counts and sample identities)
- if generator configured, expanded evidence is used or skip reason is explicit
- if generator not configured, hybrid retrieval still completes

### V2 — Seed vs expansion diagnostics (US2, FR-007/FR-008/FR-012)

**Given** a query that returns at least one seed hit.

**When** diagnostics cells run.

**Then**:
- seed count and expanded count (or added-count) are visible
- at least one row shows `chunk_id` / `parent_unit_id` / `id_str`
- if overlays loaded, at least one document overlay field is shown
- expansion warnings (if any) are printed, not dropped

### V3 — Vector-only vs hybrid comparison (US3, FR-011, SC-004)

**Given** one fixed query.

**When** both modes run.

**Then**:
- modes are labeled distinctly (`vector_only` vs `hybrid_expanded`)
- result/expansion counts are reported for both
- if expansion added nothing, notebook says so explicitly

### V4 — Graph missing / hybrid requested (Edge Cases, FR-010/FR-015, SC-005)

**Given** structural graph inputs missing or graph load failed.

**When** pure vector search runs — **then** it still works.

**When** hybrid expansion / hybrid `ask()` is requested — **then** notebook fails clearly with an unavailable-graph message (not silent vector-only under hybrid label).

### V5 — Overlays missing, graph present (Edge Cases, FR-005)

**Given** structural graph OK, overlay files missing.

**When** hybrid expansion runs.

**Then** structural expansion works and overlays are labeled unavailable; notebook does not claim authoritative currency reasoning.

### V6 — Empty seeds / empty expansion / empty generation context (Edge Cases, FR-014)

| Condition | Expected |
| --- | --- |
| Zero seed hits | skip expansion + generation; record empty context |
| Expansion returns only seeds | report zero added context; not a failure |
| No usable evidence text | generation skipped with explicit message |

### V7 — Optional graph-guided pre-filter (US4, FR-020, SC-007)

**Given** graph + overlays loaded and demo enabled.

**When** pre-filter retrieval runs.

**Then**:
- whitelist size and empty-filter status are shown
- if whitelist empty, warning is explicit and results are not silently unfiltered under a graph-guided label

### V8 — Citation safety and expansion labeling (FR-013/FR-018)

**Then**:
- external stubs / non-citation-safe nodes are not presented as citation-ready evidence
- graph expansion labels are distinct from local `expand_units` labels

## Out of scope checks (do not require for acceptance)

- Full graph verification parity with every `verify_kg.py` reconciliation assertion
- Automated answer judging / e2e metrics (`evaluate_e2e.py`)
- Neo4j persistence
- New `src/` hybrid package

## Notes

- Full in-memory graph build can take noticeable time/memory (same operational class as `scripts/verify_kg.py`). Report duration/stats; do not hide failures.
- This notebook is a hybrid pipeline **demonstration** layered on existing modules, not a replacement for dedicated verification or judged evaluation scripts (FR-017).
