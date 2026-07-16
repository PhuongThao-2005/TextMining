# Implementation Plan: Vector-Only Retrieval Evaluation Notebook

**Branch**: `008-vector-retrieval-eval-notebook` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `L_RAG/specs/008-vector-retrieval-eval-notebook/spec.md`

## Summary

Build a new, standalone Jupyter notebook (`L_RAG/notebooks/vector_retrieval_eval.ipynb`) that runs vector-only retrieval evaluation against the frozen `data/qa_final.jsonl` benchmark, entirely by composing existing, already-tested library code (`src/evaluation/eligibility.py`, `src/evaluation/metrics.py`, `src/evaluation/retriever_factory.py`, `src/retrieval/*`). The notebook contains no ad-hoc metric/eligibility logic, does not import from `L_RAG/notebooks/archive/`, and does not require the knowledge graph or hybrid fusion. It exposes a single configuration cell (top_k list, local FAISS index directory, model, score threshold, expand_units, sample limit), runs retrieval + metrics per eligible case, renders overall/by-category/by-difficulty/by-answer_type tables, and optionally persists a per-case JSONL + aggregate metrics JSON to a run-scoped `evaluation_runs/vector_only/<run_id>/` directory — mirroring the shapes `scripts/evaluate_retrieval.py` already produces.

## Technical Context

**Language/Version**: Python 3.11 (existing project interpreter; matches `src/` and `scripts/`)

**Primary Dependencies**: Jupyter/`ipynb` notebook format, `src/evaluation/*` (`eligibility.py`, `metrics.py`, `retriever_factory.py`, `io_utils.py`), `src/retrieval/*` (`VectorRetriever`, `SQLitePayloadFaissVectorStore`, `SentenceTransformerEmbedder`, `HashingEmbedder`), pandas (for tabular display of aggregate/breakdown tables — already an implicit dependency of notebook-style evaluation in this repo; used only for presentation, never as a metric source)

**Storage**: Reads `data/qa_final.jsonl` (read-only); loads a local FAISS index directory (`index.faiss` + `payloads.jsonl`, with an auto-built/refreshed `payload_cache.sqlite`) via `SQLitePayloadFaissVectorStore.load(index_dir)`, wired through `RetrieverRuntimeConfig`/`build_vector_retriever` (FR-002a). Per the `/speckit.clarify` correction, Qdrant is not used by this notebook. Optionally writes to `evaluation_runs/vector_only/<run_id>/` (per-case JSONL + metrics JSON)

**Testing**: `pytest` (existing `tests/` suite covers the reused library code: `tests/test_evaluation_eligibility.py`, `tests/test_evaluation_metrics.py`, `tests/test_evaluation_retrieval_eval_report.py`, plus `tests/retrieval/test_sqlite_faiss_store.py` for the FAISS/SQLite store). The notebook itself is validated via a smoke-test script/cell path using `HashingEmbedder` + `InMemoryVectorStore` so it can run without a populated FAISS index/model access in CI-like conditions; no new pytest suite is introduced for the notebook file itself since notebooks are not natively pytest-collectible in this repo, but any new pure-Python helper extracted for the notebook (if needed) MUST land in `src/evaluation/` with unit tests, per constitution Principle V. The FR-002a extension to `retriever_factory.py` MUST also ship with unit tests in `tests/`.

**Target Platform**: Local/dev Jupyter (matches existing `notebooks/archive/*.ipynb` and `src/retrieval/embed.ipynb` usage pattern); no server/deployment target.

**Project Type**: Single project (existing `L_RAG/` repo layout: `src/`, `scripts/`, `tests/`, `notebooks/`, `data/`, `docs/`).

**Performance Goals**: No new performance target beyond existing retrieval/metric code; notebook run time is bounded by local FAISS search + SQLite payload-cache lookup latency and QA set size (same as `scripts/evaluate_retrieval.py`).

**Constraints**: MUST NOT read/import `L_RAG/notebooks/archive/*`; MUST NOT require knowledge graph, `GraphExpansion`, `GraphTraversal`, or hybrid fusion; MUST reuse `src/evaluation/metrics.py` and `src/evaluation/eligibility.py` as sole metric/eligibility source (no reimplementation); config changes must not require editing `src/`.

**Scale/Scope**: Bounded by `data/qa_final.jsonl` size (frozen benchmark, same scale as existing CLI evaluator); single notebook file, no multi-file feature.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Legal Evidence Is Ground Truth)**: Satisfied — retrieved chunks come from `VectorRetriever`, which already resolves `chunk_id → parent_unit_id → id_str`; per-case output includes ground-truth and retrieved chunk IDs plus citation fields already exposed by `RetrievedChunk`. No new evidence path is invented.
- **Principle II (Shared Identity Across Dataset, Vector, and Graph)**: Satisfied — notebook uses the existing `chunk_id`/`parent_unit_id`/`id_str` join keys as returned by `VectorRetriever`; no new ID scheme introduced.
- **Principle III (Traceability, Reconciliation, No Silent Data Loss)**: Satisfied by design — FR-003/FR-007/FR-013 require every QA row to be classified into exactly one of eligible/skipped-unanswerable/skipped-missing-ground-truth and the counts to be visibly reported, reusing `select_eligible_cases`'s already-reconciling behavior (total = eligible + both skip counts).
- **Principle IV (Legal Correctness Over Convenience)**: N/A beyond what `VectorRetriever`/filter profiles already enforce; notebook does not add new legal-status logic.
- **Principle V (Modular, Testable, Reported Pipelines)**: Satisfied — all metric/eligibility logic stays in already-tested `src/evaluation/` modules; the notebook is a thin composition/presentation layer. If any new non-trivial helper is needed (e.g., a table-rendering function), it MUST be added to `src/evaluation/` with tests rather than living only in the notebook.
- **Principle VI (Retrieval Quality and Evaluation Are Product Requirements)**: Directly satisfied — this feature exists to provide an interactive vector-only evaluation view using the existing Recall/Hit/MRR/nDCG/Jaccard metrics.
- **No silent fallback (Workflow Gate 5)**: Satisfied by design — FR-011/FR-012 require explicit errors for missing QA file / missing or corrupt FAISS index directory rather than silently returning empty results.

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/008-vector-retrieval-eval-notebook/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command) — notebook I/O contract only
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
L_RAG/
├── notebooks/
│   ├── archive/                          # OUT OF SCOPE — do not read or modify
│   └── vector_retrieval_eval.ipynb       # NEW: this feature's notebook
├── src/
│   └── evaluation/
│       ├── eligibility.py                # reused as-is (select_eligible_cases)
│       ├── metrics.py                     # reused as-is (recall/hit/mrr/ndcg/jaccard, aggregate*)
│       ├── retriever_factory.py           # EXTENDED (FR-002a): RetrieverRuntimeConfig/build_vector_retriever gain a FAISS-backed path via SQLitePayloadFaissVectorStore.load(index_dir); Qdrant path retained but no longer the default
│       ├── io_utils.py                    # reused as-is (read_jsonl/write_jsonl/write_json/qa_id)
│       └── retrieval_eval_report.py       # reused if it fits vector-only shape (RetrievalCaseResult, ModeRunSummary, write_case_jsonl, write_metrics_json); otherwise thin new notebook-local table-building only, no metric reimplementation
├── scripts/
│   └── evaluate_retrieval.py              # reference for output shapes; not modified
├── data/
│   └── qa_final.jsonl                     # read-only input
└── evaluation_runs/
    └── vector_only/<run_id>/              # NEW: notebook's optional persisted output directory
        ├── retrieval_cases.jsonl
        └── retrieval_metrics.json
```

**Structure Decision**: Single project, additive change. The primary new artifact is one notebook file under `L_RAG/notebooks/` (sibling to, but independent of, `archive/`). `src/evaluation/retrieval_eval_report.py` already provides `RetrievalCaseResult`/`ModeRunSummary`/`write_case_jsonl`/`write_metrics_json`/`build_case_metrics_row` in a mode-agnostic shape (`RetrievalMode = "vector_only" | "hybrid"`) that this notebook can use directly with `mode="vector_only"`, avoiding duplication of `scripts/evaluate_retrieval.py`'s inline dict-building logic. Per the `/speckit.clarify` correction, one small `src/` change IS required: `src/evaluation/retriever_factory.py` (FR-002a) needs a FAISS-backed construction path via `SQLitePayloadFaissVectorStore.load(index_dir)`, since it currently only supports Qdrant and raises `ValueError` otherwise. This extension lands in already-tested `src/evaluation/` with its own unit tests, keeping the notebook itself free of business logic per constitution Principle V. If Phase 1 design finds any further gap (e.g., a table-formatting helper not covered by any existing module), it will similarly be added under `src/evaluation/` with unit tests.

## Complexity Tracking

> No Constitution Check violations identified; table intentionally omitted.
