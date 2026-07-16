# Implementation Plan: Retrieval Evaluation Notebook

**Branch**: `006-retrieval-eval-notebook` | **Date**: 2026-07-16 | **Spec**: [`spec.md`](./spec.md)
**Input**: Feature specification from [`specs/006-retrieval-eval-notebook/spec.md`](./spec.md)

## Summary

Add a new, dedicated notebook [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb) that scores **vector-only** and **hybrid** retrieval against the frozen QA benchmark using only [`src/evaluation/metrics.py`](../../src/evaluation/metrics.py) / [`aggregate`/`aggregate_by`]. Vector-only reuses the production FAISS stack (`SQLitePayloadFaissVectorStore` + `SentenceTransformerEmbedder` + `VectorRetriever`). Hybrid follows [`docs/spec/GRAPH_MODULE.md`](../../docs/spec/GRAPH_MODULE.md) §10 as the primary sequence: an unfiltered vector pre-pass supplies non-leaking `GraphTraversal` start IDs, traversal (+ optional overlays/ContextBuilder) produces a document whitelist, vector search runs filtered by that whitelist, and `GraphExpansion` expands the filtered hits; the fused ranked list (seeds → expansion → extra traversal chunks, keep-first dedupe) is scored with the same metric suite as vector-only. New pure helpers land in `src/evaluation/` for eligibility, fusion, hybrid orchestration, and reporting so the notebook itself stays a thin, testable orchestration layer; hybrid unavailability is always explicit and vector-only always remains runnable.

## Technical Context

**Language/Version**: Python 3.11 (project `pyproject.toml`), Jupyter notebook (`.ipynb`)
**Primary Dependencies**: `src/evaluation/{metrics,io_utils}.py` (existing, unmodified), `src/retrieval/{retriever,sqlite_faiss_store,embeddings,schema}.py` (existing, unmodified), `src/knowledge_graph/{facade,traversal,expansion,context_schema,persist}.py` (existing, unmodified); new pure helper module(s) under `src/evaluation/`
**Storage**: Read-only `data/benchmark/qa_final.jsonl` (frozen benchmark), FAISS index artifacts under a configurable `INDEX_DIR` (`payloads.jsonl` / `payload_cache.sqlite` / FAISS index files), structural graph pickle `data/graph/knowledge_graph.gpickle` (feature 004/005), optional overlay sources. Writes new artifacts only under a configurable `OUT_DIR` (default `evaluation_runs/retrieval_notebook/<run_name>/`)
**Testing**: `pytest` for new pure helpers under `tests/` (eligibility, fusion order, metric-row wiring, hybrid-unavailable guard, no-GT-start leakage guard); manual notebook run against real FAISS + graph artifacts for full acceptance (no contracts dir — in-process notebook + module calls, not a network API)
**Target Platform**: Local Python / Jupyter and Colab (project root or `notebooks/`), reusing path-resolution conventions from features 001/003/005
**Project Type**: Single project — notebook + `src/evaluation` library helpers + tests (no frontend/backend split)
**Performance Goals**: No new numeric targets beyond FR/SC; must support both a smoke sample (default configurable N, e.g. 20+) and a full-benchmark run without notebook code edits
**Constraints**: No silent hybrid fallback (Constitution + FR-011); no ground-truth leakage into traversal starts (FR-003g); no ad-hoc metric reimplementation (FR-004); no modification of the frozen benchmark file (FR-017); no hardcoded machine-specific absolute paths (FR-016); E2E generation metrics out of scope (FR-018)
**Scale/Scope**: One new notebook, one or more new small pure-helper modules under `src/evaluation/`, corresponding unit tests; no changes to existing CLI (`scripts/evaluate_retrieval.py`, `scripts/evaluate_e2e.py`) or to `retriever_factory.py`'s existing Qdrant contract

## Constitution Check

| Principle | Applicability | Assessment |
| --- | --- | --- |
| I. Legal Evidence Is Ground Truth | Applies — retrieved chunks are evidence used for scoring, not display, but ground truth must remain the citable authority | PASS. All scoring uses `chunk_id` against `ground_truth.chunk_ids`; ground truth is read-only and never used to drive retrieval (FR-020, FR-003g). No new citation-facing claims are produced by this feature. |
| II. Shared Identity Across Dataset, Vector, and Graph | Applies directly — hybrid path crosses vector, graph, and benchmark identity spaces | PASS. `chunk_id → parent_unit_id → id_str` is preserved end-to-end: vector pre-pass and filtered search use existing `VectorRetriever` payload fields; traversal starts/whitelist use `id_str`; expansion returns `chunk_id`s; fusion/metrics compare `chunk_id` sets only (data-model.md §1, §3). No opaque IDs introduced. |
| III. Traceability, Reconciliation, and No Silent Data Loss | Applies — eligibility skips, empty filters, empty pre-pass starts, per-case errors | PASS. `EligibilitySummary` counts every row into eligible/skipped_unanswerable/skipped_missing_ground_truth (no silent drops); `HybridDiagnostics` records empty-filter/empty-start/zero-added conditions explicitly; per-case retrieval errors are recorded and the run continues (FR-014, FR-015, Edge Cases). |
| IV. Legal Correctness Over Convenience | Partially applies — no new legal-status/validity reasoning is introduced by this feature | PASS (not applicable beyond pass-through). Overlays/validity filters, when used, are consumed via existing `KnowledgeGraphFacade` contracts unchanged; this feature does not add new authority/currency logic. |
| V. Modular, Testable, Reported Pipelines | Applies directly — this feature is itself an evaluation pipeline stage | PASS. Non-trivial logic (eligibility, fusion, hybrid orchestration, report writing) is extracted into small pure helper functions under `src/evaluation/` with unit tests (research R8, R12); notebook stays thin orchestration; artifacts (`*_cases.jsonl`, `*_metrics.json`, `*_report.md`) report counts and configuration for every run. |
| VI. Retrieval Quality and Evaluation Are Product Requirements | Applies directly — this is the core purpose of the feature | PASS. Uses the shared evaluation module exclusively for metrics (FR-004, SC-003); evaluates both vector-only and hybrid so architecture claims are measurable; never mislabels degraded/partial hybrid as full hybrid (FR-011, FR-003c, SC-007). |

**No silent fallback (workflow gate)**: PASS. Hybrid requires both `GraphTraversal` and `GraphExpansion` constructible from a loaded structural graph; any missing prerequisite yields an explicit `hybrid_available=False` with a stated reason rather than unfiltered vector results relabeled as hybrid (research R7; data-model.md §5).

**Result**: No violations. No entries required in Complexity Tracking.

### Post-design re-check

Re-evaluated after Phase 1 ([`data-model.md`](./data-model.md), [`quickstart.md`](./quickstart.md)): entity shapes (`EligibleCase`, `TraversalStartSet`, `HybridDiagnostics`, `HybridFusionResult`, `RetrievalCaseResult`, `ModeRunSummary`, `ComparisonSummary`) introduce no new identity types, no new legal-status reasoning, and no metric reimplementation — they wrap existing module calls and preserve `chunk_id`/`id_str` end-to-end. Constitution Check result is unchanged: **PASS**, no complexity deviations.

## Project Structure

### Documentation (this feature)

```text
specs/006-retrieval-eval-notebook/
├── spec.md              # already exists (input)
├── research.md          # Phase 0 output (done)
├── data-model.md         # Phase 1 output (done)
├── quickstart.md         # Phase 1 output (this plan)
├── plan.md               # this file
├── checklists/
│   └── requirements.md   # already exists
└── tasks.md              # generated by /speckit.tasks (not by this command)
```

### Source Code (repository root)

```text
L_RAG/
├── notebooks/
│   └── retrieval_eval.ipynb          # NEW — dedicated evaluation notebook (config, load, run, report cells)
├── src/
│   └── evaluation/
│       ├── metrics.py                  # existing, unmodified — sole metric source of truth
│       ├── io_utils.py                 # existing, unmodified
│       ├── retriever_factory.py        # existing, unmodified (Qdrant-only CLI contract; not used by this notebook)
│       ├── eligibility.py              # NEW — select_eligible_cases(), EligibleCase/EligibilitySummary
│       ├── hybrid_fusion.py            # NEW — fuse_hybrid_chunk_ids(), build_traversal_starts()
│       └── retrieval_eval_report.py    # NEW — build_case_metrics_row(), ModeRunSummary/ComparisonSummary builders, report writers
├── tests/
│   ├── test_evaluation_metrics.py      # existing, unmodified (flat convention for src/evaluation/*)
│   ├── test_evaluation_eligibility.py  # NEW — eligibility skip/counter behavior
│   ├── test_evaluation_hybrid_fusion.py # NEW — fusion order/dedupe, traversal-start leakage guard
│   └── test_evaluation_retrieval_eval_report.py # NEW — metric-row wiring, hybrid-unavailable guard, comparison builder
└── scripts/
    ├── evaluate_retrieval.py           # existing, unmodified — CLI vector-only contract remains authoritative reference
    └── evaluate_e2e.py                 # existing, unmodified — out of scope for this feature
```

**Structure Decision**: New helper modules live flat under `src/evaluation/` (three focused files rather than one large module or a new top-level package), following the size/scope precedent of the existing `metrics.py` / `io_utils.py` / `retriever_factory.py` trio and research R8's "no new `src/hybrid_eval/` package" decision. New tests follow the existing flat `tests/test_evaluation_metrics.py` naming convention (`tests/test_evaluation_<topic>.py`) rather than introducing a nested `tests/evaluation/` folder, for consistency with the one existing evaluation test file. The notebook itself is the only new file under `notebooks/`; no changes are made to `faiss_retrieval_ready.ipynb`, `retriever_factory.py`, or either CLI script.

## Implementation Outline (for tasks phase)

1. Add `src/evaluation/eligibility.py`: `EligibleCase`, `EligibilitySummary`, `select_eligible_cases(rows, sample_limit)` mirroring `scripts/evaluate_retrieval.py` skip logic; unit tests.
2. Add `src/evaluation/hybrid_fusion.py`: `TraversalStartSet`, `build_traversal_starts(prepass_hits, mode, max_starts)` (no GT access) and `HybridFusionResult`, `fuse_hybrid_chunk_ids(seeds, expansion_chunks, traversal_chunks)`; unit tests for order/dedupe/leakage guard.
3. Add `src/evaluation/retrieval_eval_report.py`: `build_case_metrics_row(retrieved_ids, gt_ids, top_k_list)` (thin wrapper over `metrics.py`), `ModeRunSummary` / `ComparisonSummary` builders, and markdown report writer(s) reusing `scripts/evaluate_retrieval.py`'s `write_report` / `_group_table` patterns; unit tests.
4. Build `notebooks/retrieval_eval.ipynb`:
   - Config cell exposing the full `EvalRunConfig` surface (research R13), with path resolution that works from project root or `notebooks/`.
   - Preflight cell: QA path, FAISS index artifacts, graph pickle/JSONL availability; clear failure messages per Edge Cases.
   - Vector-only run cell: build `VectorRetriever` over the FAISS stack; iterate eligible cases; score with `build_case_metrics_row`; write `vector_only_*` artifacts.
   - Hybrid run cell: unfiltered pre-pass → `build_traversal_starts` → `KnowledgeGraphFacade.traverse` per start → whitelist/`GraphGuidedFilter` → filtered vector search → `GraphExpansion.expand` → `fuse_hybrid_chunk_ids` → score → write `hybrid_*` artifacts; explicit hybrid-unavailable branch when graph/traversal/expansion cannot be constructed.
   - Comparison cell: build and display/write `ComparisonSummary` when both modes ran; otherwise show vector-only-only note.
5. Validate against [`quickstart.md`](./quickstart.md) scenarios V1–V8 (happy paths + edge cases) using real FAISS artifacts and, where available, a real graph pickle.
6. Run `pytest` for the new test files plus the existing evaluation/retrieval/knowledge_graph suites to confirm no regressions.

## Complexity Tracking

*No Constitution Check violations — this section intentionally left empty.*
