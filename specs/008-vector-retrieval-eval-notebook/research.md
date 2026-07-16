# Phase 0 Research: Vector-Only Retrieval Evaluation Notebook

All items from the spec's Clarifications section are already resolved (see `spec.md` → Clarifications, Session 2026-07-16, including the FAISS/SQLite-not-Qdrant correction). This document records the remaining implementation-level decisions needed before Phase 1 design.

## R1: Reuse `retrieval_eval_report.py` vs. duplicate `evaluate_retrieval.py`'s inline logic

- **Decision**: Reuse `src/evaluation/retrieval_eval_report.py` (`RetrievalCaseResult`, `ModeRunSummary`, `build_case_metrics_row`, `write_case_jsonl`, `write_metrics_json`) with `mode="vector_only"`.
- **Rationale**: This module already exists, is unit-tested (`tests/test_evaluation_retrieval_eval_report.py`), and defines a `RetrievalMode = Literal["vector_only", "hybrid"]` shape specifically anticipating a vector-only case. Using it avoids reimplementing per-case dict shaping and keeps a single source of truth for both this notebook and any hybrid notebook that reuses the same module. It also directly satisfies FR-004 ("no ad-hoc formulas reimplemented") and FR-008's field-shape requirement.
- **Alternatives considered**: Duplicate `scripts/evaluate_retrieval.py`'s inline `dict`-building code directly in the notebook. Rejected — this would be an ad-hoc reimplementation of already-existing, tested shaping logic, increasing drift risk between the CLI script and notebook outputs, and violating the spirit of FR-004/FR-005 (avoid ad-hoc formulas) even though the low-level metric functions would still come from `metrics.py`.

## R2: Vector store / embedder wiring — FAISS + SQLite payload cache, not Qdrant

- **Decision**: Extend `src/evaluation/retriever_factory.py`'s `RetrieverRuntimeConfig`/`build_vector_retriever` to add a `store: Literal["faiss", "qdrant"] = "faiss"` construction path that loads [`SQLitePayloadFaissVectorStore.load(index_dir)`](../../../src/retrieval/sqlite_faiss_store.py:289) and wires it into `VectorRetriever` alongside the existing embedder logic (`HashingEmbedder` when `dev_hashing=True`, else `SentenceTransformerEmbedder`). The notebook's configuration cell exposes `INDEX_DIR` (default `data/faiss_index/`) instead of `QDRANT_URL`/`QDRANT_API_KEY`/`COLLECTION_NAME`.
- **Rationale**: Per `/speckit.clarify` correction (2026-07-16): this notebook must retrieve from the local FAISS index (`index.faiss` + `payloads.jsonl`) with its SQLite payload cache (`payload_cache.sqlite`), matching the architecture already used by the hybrid notebook patchers (`scripts/_patch_faiss_hybrid_notebook.py`, `scripts/_patch_faiss_colab_safe_notebook.py`) via [`SQLitePayloadFaissVectorStore`](../../../src/retrieval/sqlite_faiss_store.py:263), which already implements the same `VectorStore` ABC as `QdrantVectorStore` and is therefore a drop-in `store=` argument for `VectorRetriever`. `retriever_factory.py` currently hard-codes Qdrant and explicitly raises `ValueError` for any other `store` value (see `build_vector_retriever`'s `if runtime.store != "qdrant": raise ValueError(...)`), so this factory function is the one non-notebook code change this feature requires (tracked as FR-002a; still satisfies constitution Principle V since the change lands in already-tested `src/evaluation/` with new unit tests, not notebook-local logic).
- **Alternatives considered**:
  - Constructing `SQLitePayloadFaissVectorStore` + `VectorRetriever` directly in the notebook, bypassing `retriever_factory.py` entirely. Rejected — this would duplicate wiring logic already centralized in the factory and diverge from the pattern used by `evaluate_retrieval.py`/other evaluation entry points; extending the factory keeps one source of truth for both CLI and notebook.
  - Keeping Qdrant as the only backend and requiring the user to first export the FAISS index into Qdrant. Rejected outright by the user's explicit clarification — Qdrant is not used by this notebook.

## R3: Eligibility filtering

- **Decision**: Use `src/evaluation/eligibility.py`'s `select_eligible_cases(rows, sample_limit)` directly; do not reimplement `_is_unanswerable`/ground-truth-emptiness checks in the notebook.
- **Rationale**: Directly satisfies FR-003 and User Story 2's independent test (must match `select_eligible_cases`'s counts exactly, which is trivially true if the same function is called). Already unit-tested (`tests/test_evaluation_eligibility.py`), including the "every row classified exactly once" invariant.
- **Alternatives considered**: None seriously considered — reimplementing this logic would directly contradict FR-003.

## R4: Per-run output directory naming

- **Decision**: Default output directory `evaluation_runs/vector_only/<run_id>/` where `run_id` is a notebook-generated timestamp (e.g., `time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())`), configurable/overridable in the config cell. Two files written on persist: `retrieval_cases.jsonl` and `retrieval_metrics.json` (names mirroring `scripts/evaluate_retrieval.py`'s `retrieval_cases.jsonl` / `retrieval_metrics.json` for consistency and potential downstream tooling reuse per SC-004).
- **Rationale**: Matches the Assumptions section's "analogous to `--out-dir`" requirement and keeps file names consistent with the existing CLI script's artifacts so downstream reporting tools (e.g., anything that already parses `retrieval_metrics.json`) work unmodified.
- **Alternatives considered**: Reusing `evaluation_runs/retrieval/` (the CLI script's default) directly. Rejected — would risk overwriting/mixing CLI-script runs with notebook runs; a dedicated `vector_only/` subtree keeps notebook-run artifacts clearly separated and labeled, reinforcing FR-010 (label output as vector-only).

## R5: Presentation of tables (pandas vs. plain print)

- **Decision**: Use `pandas.DataFrame` for overall/by-category/by-difficulty/by-answer_type table display when pandas is available in the environment; degrade to plain-text/dict printing if pandas is not installed, with the underlying aggregate dicts always coming unmodified from `metrics.aggregate`/`metrics.aggregate_by`.
- **Rationale**: `pandas` gives the best interactive-table UX in Jupyter (rendered HTML tables) without touching any metric computation; it is presentation-only and does not affect FR-004/FR-005's "sole metric source" requirement since the DataFrame is built directly from `aggregate`/`aggregate_by` outputs, not recomputed.
- **Alternatives considered**: Hand-rolled Markdown table printing (as `scripts/evaluate_retrieval.py`'s `write_report`/`_group_table` do for the `.md` report file). Kept as an option for the persisted Markdown report but not as the primary interactive display, since Jupyter table rendering via pandas is friendlier for exploration (User Story 3's sensitivity-analysis use case).

## R6: Guarding against archive-notebook coupling

- **Decision**: The notebook's first cell / header MUST explicitly state it does not import from `L_RAG/notebooks/archive/`, and no cell may contain such an import. This is enforced by code review / self-check rather than an automated notebook linter, since no notebook-content test harness currently exists in this repo.
- **Rationale**: Directly satisfies FR-009 and SC-005. Given there's no existing tooling to statically scan notebook cell source for import statements, and adding one would be disproportionate to this feature's scope, a manual/checklist-based guarantee (backed by the plan's "no `archive/` reads at any phase" instruction already followed during planning) is sufficient.
- **Alternatives considered**: Writing a small pytest that parses the `.ipynb` JSON and greps cell sources for `archive` imports. Considered as an optional Phase 2 task (tasks.md) rather than a Phase 0 blocking decision — it's a nice-to-have regression guard, not required to satisfy the FR/SC on first delivery.

## Summary

No `NEEDS CLARIFICATION` markers remain. All decisions favor maximal reuse of existing, tested `src/evaluation/` and `src/retrieval/` code, keeping the notebook itself as a thin configuration + orchestration + presentation layer.
