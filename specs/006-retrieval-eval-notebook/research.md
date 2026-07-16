# Phase 0 Research: Retrieval Evaluation Notebook

## R1: Primary surface — new dedicated notebook, not demo notebook extension

**Decision**: Create a **separate** notebook [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb). Do **not** fold official scored evaluation into [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb).

**Rationale**: FR-001 requires a dedicated retrieval-evaluation notebook distinct from interactive FAISS/hybrid demos. Demo notebook optimizes for smoke queries, Colab profiles, and generation. Evaluation needs frozen-benchmark iteration, skip counters, evaluation-module metrics, mode-labeled artifacts, and dual-mode comparison. Mixing those concerns into the demo notebook risks silent hybrid labels, generation side effects, and Colab opt-in gates interfering with scored runs.

**Alternatives considered**:
- Extend `faiss_retrieval_ready.ipynb` with an evaluation section — rejected by FR-001 and by demo vs eval separation in Assumptions.
- Only extend CLI `scripts/evaluate_retrieval.py` — rejected: feature is notebook surface; CLI remains vector-oriented and Qdrant-factory-bound.

## R2: Metric source of truth — evaluation module only

**Decision**: Score every official case with [`src/evaluation/metrics.py`](../../src/evaluation/metrics.py):

- `recall_at_k`, `hit_at_k`, `mrr_at_k`, `ndcg_at_k`, `jaccard_at_k`
- `aggregate`, `aggregate_by`

Use [`src/evaluation/io_utils.py`](../../src/evaluation/io_utils.py) for JSONL/JSON IO and `qa_id`. Mirror eligibility and artifact shapes from [`scripts/evaluate_retrieval.py`](../../scripts/evaluate_retrieval.py) (skip unanswerable / missing GT; write cases + metrics + markdown report).

**Rationale**: FR-004, FR-006–FR-008, SC-003, and Constitution Principle VI require product evaluation hooks, not ad-hoc notebook formulas. CLI already encodes the accepted retrieval-track contract in [`docs/spec/EVALUATION_MODULE.md`](../../docs/spec/EVALUATION_MODULE.md).

**Alternatives considered**:
- Reimplement metrics in notebook cells for speed — rejected by FR-004 / SC-003.
- Call `evaluate_retrieval.py` as a subprocess from the notebook — rejected for hybrid mode (CLI has no hybrid path) and poor interactive diagnostics.

## R3: Vector-only runtime — FAISS notebook stack, not Qdrant-only factory

**Decision**: Vector-only evaluation builds production-style `VectorRetriever` over the **FAISS notebook stack**:

- `SQLitePayloadFaissVectorStore` (preferred when `payload_cache.sqlite` present)
- `SentenceTransformerEmbedder` matching the index model
- `VectorIndexConfig` + `VectorRetriever.retrieve(...)`

Do **not** hard-require Qdrant via current [`retriever_factory.build_vector_retriever`](../../src/evaluation/retriever_factory.py) (Qdrant-only for CLI). Optionally extend factory later with a FAISS/store backend; not required for notebook v1 if notebook constructs the same production types.

**Rationale**: Project interactive path and Colab packs are FAISS-based (features 001/003/005). Spec Assumptions say reuse production vector retrieval path used by FAISS notebook stack. Existing factory raises if `store != "qdrant"`, so notebook must not depend on that as sole constructor.

**Alternatives considered**:
- Force Qdrant for eval notebook — rejected: mismatches local/Colab artifact packs and demo index.
- HashingEmbedder default — rejected: invalidates real FAISS scores; keep only for unit tests.

## R4: Hybrid operational sequence — GRAPH_MODULE §10 primary path

**Decision**: Official hybrid evaluation follows [`docs/spec/GRAPH_MODULE.md`](../../docs/spec/GRAPH_MODULE.md) §10 as the **primary** sequence:

```text
1. Unfiltered vector pre-pass on question text
   → seed chunk IDs (vector rank order)
   → map seeds to graph start IDs (chunk → parent_unit_id → id_str / document starts as runtime requires)
2. GraphTraversal from those starts (modes/caps per §6; default basis max_depth=3)
   → optional OverlayBundle / ContextBuilder
   → GraphGuidedFilter whitelist (id_str set)
3. Vector search with graph_guided / id_str_filter whitelist (no silent full-corpus fallback)
4. GraphExpansion on filtered vector hits (§7: provision window, PROVISION_NEXT, max_context)
5. Fuse ranked chunk IDs for metrics:
   seeds (filtered vector order) → expansion chunks → any extra traversal-resolved chunk IDs
   dedupe keep first occurrence
```

Both **GraphTraversal** and **GraphExpansion** are required constituents of full hybrid (FR-003, FR-003a–g).

**Rationale**: Spec clarifications + FR-003f/g override the demo notebook’s default vector-first-expand-only story (feature 003 R1). Evaluation measures the product hybrid contract under §10, not expansion-only convenience demos.

**Alternatives considered**:
- Expansion-only hybrid (003 primary demo path) — rejected for *scored* hybrid by FR-003f and clarify session.
- Traversal-only without expansion — rejected by FR-003a/c.
- Ground-truth IDs as traversal starts — rejected by FR-003g (label leakage).

## R5: Traversal start mapping from vector pre-pass

**Decision**: Map unfiltered pre-pass hits to graph starts as follows (deterministic, no GT):

1. Collect pre-pass `chunk_id`s in vector rank order.
2. Resolve each hit’s `id_str` (document) from payload; also retain `parent_unit_id` / `chunk_id`.
3. Prefer **document `id_str` starts** for cross-document modes (`basis`, `guidance`, `validity`, `neighbors`).
4. For `structure` mode, starts may be document / provision / chunk IDs as supported by `GraphTraversal.traverse_structure`.
5. Deduplicate starts keep-first; cap start count via config (e.g. top M pre-pass docs).
6. If pre-pass yields zero usable starts: record empty-start diagnostics; **do not** substitute ground-truth; mark case hybrid-failed/unavailable or score only if a legitimate non-leaking path remains — never silent full-corpus hybrid.

Default traversal mode for aggregate hybrid eval: `basis` with `max_depth=3` (GRAPH_MODULE §6). Config may select among `basis|guidance|validity|structure|neighbors` without redefining semantics.

**Rationale**: FR-003g + Edge Cases. Cross-document traversal APIs are document-centric; structure mode accepts multi-level IDs. Seed-derived starts prevent label leakage while remaining reproducible.

**Alternatives considered**:
- Always start from chunk IDs only — incomplete for cross-document modes that key on documents.
- Use GT document/provision/chunk IDs when pre-pass empty — rejected (leakage).

## R6: Fusion order and scoring list

**Decision**: Hybrid `retrieved_chunk_ids` used for metrics:

```text
ordered = []
append unique: filtered_vector_seed_chunk_ids  # vector rank
append unique: graph_expansion.ordered_context_chunks
append unique: traversal-resolved chunk IDs not already present
# keep-first dedupe throughout
```

Truncate metrics at configured k using evaluation-module semantics (same as CLI when k > list length).

**Rationale**: FR-003d; preserves seed rank for MRR/nDCG while still counting expansion/traversal evidence in recall/hit/jaccard.

**Alternatives considered**:
- Score expansion-only list without seeds — rejected: loses seed rank and understates vector contribution.
- Re-rank fused list with a new scorer — out of scope; no undocumented ranker.

## R7: No silent hybrid fallback

**Decision**: Hybrid evaluation is available only when **both** GraphTraversal and GraphExpansion can be constructed from a loaded structural graph (pickle preferred via feature 004/005, or explicit JSONL rebuild). Missing either service, missing graph, empty silent-fallback risk, or hybrid guard failure → hybrid **unavailable** with explicit message. Never label pure unfiltered vector results as `hybrid`. Never claim full hybrid for expansion-only or traversal-only partial paths without stating the missing service.

Vector-only must remain runnable when hybrid is unavailable (FR-011, SC-007, Constitution III / no silent fallback).

**Rationale**: Spec FR-011, Edge Cases, constitution workflow gate.

## R8: Where orchestration logic lives

**Decision**: Prefer **thin notebook** plus small **testable pure helpers** under `src/evaluation/` for non-trivial shared logic:

| Helper (proposed) | Responsibility |
| --- | --- |
| Eligibility / case iteration | Skip unanswerable + missing GT; sample limit; counters |
| Metric row builder | Call metrics.py for each k; attach metadata |
| Hybrid fusion | Keep-first fuse seeds/expansion/traversal IDs |
| Hybrid retrieve step | Pre-pass → traverse → whitelist → filtered vector → expand → fuse + diagnostics |
| Summary / report writer | Aggregate + markdown tables (reuse CLI report patterns) |

Notebook owns config cells, FAISS/graph load, run orchestration, comparison display, path resolution.

**Rationale**: Constitution Principles V–VI: evaluation is a product requirement; fusion/eligibility/skip logic is easy to get wrong and should be unit-tested. Unlike pure demo feature 003, this feature’s scoring path must be trustworthy (SC-003). Keep helpers pure and store-agnostic where possible.

**Alternatives considered**:
- All logic notebook-only — rejected: no pytest surface for fusion/leakage guards.
- New `src/hybrid_eval/` package — overscoped; evaluation package already owns metrics/IO/factory.

## R9: Graph load policy for eval notebook

**Decision**: Align with feature 005 preferences:

1. Prefer structural pickle `data/graph/knowledge_graph.gpickle` via `KnowledgeGraphFacade.load_graph` / `load_knowledge_graph`.
2. Optional JSONL rebuild via `build_graph()` only when user opts in (heavy).
3. Overlays optional for hybrid structural success; when present, join at query time for ContextBuilder filtering; when absent, build whitelist from traversal document IDs with explicit overlays-unavailable diagnostic (still full hybrid if Traversal + Expansion present).
4. Preflight QA path, FAISS artifacts, graph pickle/JSONL before runs.

**Rationale**: Reuse portable graph artifact; avoid forcing full JSONL rebuild for every eval session.

## R10: Benchmark path defaults

**Decision**:

- Default config path: `data/benchmark/qa_final.jsonl` (spec FR-005).
- Allow override in config cell.
- Preflight: if default missing, surface clear error; document that some checkouts may place the file at `data/qa_final.jsonl` — user must set override, not silent auto-redirect that hides misconfiguration (fail clearly if configured path missing). Optional convenience: if and only if config still points at default and default missing but `data/qa_final.jsonl` exists, print a **single explicit warning** and use that path — never invent metrics on a wrong file without message.

**Rationale**: Spec Edge Cases + FR-005. Observed workspace currently has `data/qa_final.jsonl` without `data/benchmark/`; plan must not hardcode machine-specific absolutes (FR-016).

## R11: Artifacts and comparison

**Decision**: Under configurable `OUT_DIR` (default e.g. `evaluation_runs/retrieval_notebook/<timestamp or run_name>/`):

| Mode | Cases | Metrics JSON | Report |
| --- | --- | --- | --- |
| vector_only | `vector_only_cases.jsonl` | `vector_only_metrics.json` | `vector_only_report.md` |
| hybrid | `hybrid_cases.jsonl` | `hybrid_metrics.json` | `hybrid_report.md` |
| both | plus `comparison.md` / `comparison_metrics.json` with side-by-side overall@k |

Each case row includes `mode`, GT chunk IDs, ranked retrieved IDs, per-k metrics, hybrid diagnostics (whitelist size, visited IDs sample, expansion counts, empty-filter/empty-start flags). Summary includes evaluated / skipped_unanswerable / skipped_missing_gt / error counts.

**Rationale**: FR-010, FR-013, FR-014, FR-019, SC-004/SC-005.

## R12: Contracts directory and test scope

**Decision**:

- No network/API `contracts/` directory (in-process notebook + evaluation helpers).
- Unit tests for pure helpers: eligibility, fusion order, metric-row wiring (mock retrieved IDs), hybrid unavailable guards, no-GT-start leakage.
- Manual/quickstart validation for full notebook run against real FAISS + QA sample.
- Do **not** replace CLI `evaluate_retrieval.py` or `evaluate_e2e.py`; E2E generation metrics remain out of scope (FR-018).

**Rationale**: Same notebook-feature pattern as 001/003/005 for contracts; stronger unit-test obligation than pure demo because of Principle VI.

## R13: Config surface (notebook cell)

**Decision**: Config cell exposes at least:

```text
QA_PATH, OUT_DIR, TOP_K_LIST, SAMPLE_LIMIT (None = full)
FILTER_PROFILE, SCORE_THRESHOLD, TOP_K_RETRIEVE, TOP_N
INDEX_DIR, EMBEDDING_MODEL
RUN_VECTOR_ONLY, RUN_HYBRID
GRAPH_PICKLE_PATH, V2_DATA_DIR, ALLOW_JSONL_GRAPH_REBUILD
TRAVERSAL_MODE, TRAVERSAL_MAX_DEPTH, PREPASS_TOP_N, MAX_TRAVERSAL_STARTS
HYBRID_MAX_HOP, HYBRID_MAX_CONTEXT
AS_OF_DATE (overlays), LOCAL_EXPAND_UNITS (default False for scored hybrid)
```

Record full config snapshot into metrics JSON for reproducibility.

## R14: Resolved unknowns (no remaining NEEDS CLARIFICATION)

| Topic | Resolution |
| --- | --- |
| Hybrid definition | Traversal + Expansion; §10 primary sequence |
| Start IDs | Unfiltered vector pre-pass only; never GT |
| Fusion | seeds → expansion → traversal; keep-first |
| Metrics | evaluation.metrics only |
| Vector backend | FAISS production stack |
| Notebook vs CLI | New notebook; CLI unchanged |
| E2E answers | Out of scope |
| Silent fallback | Forbidden |
