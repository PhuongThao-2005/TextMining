# Quickstart: Vector-Only Retrieval Evaluation Notebook

This guide validates [`vector_retrieval_eval.ipynb`](../../notebooks/vector_retrieval_eval.ipynb:1) end-to-end. For field-level shapes, see [`data-model.md`](./data-model.md:1) and [`contracts/notebook-io-contract.md`](./contracts/notebook-io-contract.md:1).

## Prerequisites

- Python environment with this repo's dependencies installed (`L_RAG/pyproject.toml`), plus Jupyter (`jupyter` / `notebook` or the VS Code notebook extension).
- Repo checked out with `data/qa_final.jsonl` present at the repo root's `data/` directory.
- For the **smoke-test scenario**: no external services required.
- For the **full-run scenario**: a populated local FAISS index directory (`INDEX_DIR`, default `data/faiss_index/`, containing `index.faiss` + `payloads.jsonl`; see [`scripts/build_vector_index.py`](../../scripts/build_vector_index.py:1)) and network access to download/load the configured embedding model (default `intfloat/multilingual-e5-large`). Qdrant is not used by this notebook.

## Scenario A — Smoke test (no populated FAISS index/model required)

Validates User Story 1's "Independent Test" using [`RetrieverRuntimeConfig.dev_hashing`](../../src/evaluation/retriever_factory.py:9) (per [`data-model.md` §6](./data-model.md:37)), which routes [`build_vector_retriever`](../../src/evaluation/retriever_factory.py:22) to an in-memory hashing-embedder backend instead of a real FAISS index/model.

1. Open [`vector_retrieval_eval.ipynb`](../../notebooks/vector_retrieval_eval.ipynb:1) in Jupyter.
2. In the configuration cell, set:
   - `DEV_HASHING = True`
   - `SAMPLE_LIMIT = 25` (keeps the smoke test fast)
   - Leave other defaults as-is.
3. Run all cells top to bottom.
4. **Expected outcome**:
   - No exception raised; no cell references the knowledge graph, `GraphExpansion`, `GraphTraversal`, or hybrid fusion (FR-002).
   - An overall metrics table is displayed for the configured `TOP_K_LIST` (default `[1, 5, 10]`), plus breakdown tables by `category`, `difficulty`, and `answer_type` (FR-005).
   - The run summary shows total rows, evaluated count, skipped-unanswerable count, and skipped-missing-ground-truth count (FR-007), and states the `SAMPLE_LIMIT` was applied (US2 scenario 3).
   - The notebook header/output clearly labels the run as "vector-only" (FR-010).

## Scenario B — Full run against a local FAISS index

Validates User Story 1's primary acceptance scenario and User Story 2's eligibility-count parity.

1. Ensure `INDEX_DIR` points at a directory containing `index.faiss` and `payloads.jsonl` (see [`scripts/build_vector_index.py`](../../scripts/build_vector_index.py:1)); [`SQLitePayloadFaissVectorStore.load(index_dir)`](../../src/retrieval/sqlite_faiss_store.py:289) auto-builds/refreshes `payload_cache.sqlite` on first load.
2. In the configuration cell, set:
   - `DEV_HASHING = False`
   - `INDEX_DIR`, `MODEL_NAME` to match your deployment.
   - `SAMPLE_LIMIT = None` (evaluate all eligible cases).
3. Run all cells top to bottom.
4. **Expected outcome**:
   - Overall and breakdown metrics tables are produced (SC-001).
   - Per-case output includes `qa_id`, question, ground-truth chunk IDs, retrieved chunk IDs, and per-k metrics (Acceptance Scenario 2 of US1).
   - Skipped-unanswerable and skipped-missing-ground-truth counts match what [`select_eligible_cases`](../../src/evaluation/eligibility.py:48) computes independently for `data/qa_final.jsonl` (SC-002) — cross-check by running:
     ```python
     from evaluation.io_utils import read_jsonl
     from evaluation.eligibility import select_eligible_cases
     rows = list(read_jsonl(Path("data/qa_final.jsonl")))
     summary = select_eligible_cases(rows, sample_limit=None)
     print(summary.total_rows, len(summary.eligible), summary.skipped_unanswerable, summary.skipped_missing_ground_truth)
     ```
     Compare this against the notebook's own reported counts (FR-007).

## Scenario C — Config-only experimentation (no `src/` edits)

Validates User Story 3.

1. With Scenario A or B already run once, change **only** the configuration cell: e.g. `TOP_K_LIST = [1, 3]` and a different `SCORE_THRESHOLD`.
2. Re-run the retrieval and evaluation cells (not the whole kernel).
3. **Expected outcome**:
   - The metrics table's columns/values reflect the new `TOP_K_LIST` and threshold (SC-003).
   - No file under `src/` was edited.
   - Per-case rows from the previous run are not mixed into the new aggregate (FR-014) — the evaluated count and displayed rows correspond only to the current configuration.

## Scenario D — Error handling

Validates FR-011/FR-012/FR-013.

1. **Missing QA file**: Temporarily set `QA_PATH` to a nonexistent path and run the load cell. **Expected**: a clear error naming the missing path, raised at the load cell (not several cells later).
2. **Missing/corrupt FAISS index**: Set `DEV_HASHING = False` and point `INDEX_DIR` at a nonexistent or incomplete directory (missing `index.faiss` or `payloads.jsonl`). Run the retrieval cell. **Expected**: a clear load/configuration error (via [`SQLitePayloadFaissVectorStore.load`](../../src/retrieval/sqlite_faiss_store.py:289)) surfaced at the retrieval step, not a silent empty-result case.
3. **Zero eligible cases**: Point `QA_PATH` at a QA file where every row is unanswerable or missing ground truth (or filter `SAMPLE_LIMIT = 0`). **Expected**: the summary reports zero evaluated cases with skip-reason counts, without raising during aggregation (FR-013; backed by [`aggregate([], metric_keys)`](../../src/evaluation/metrics.py:110) returning a zero-count row).

## Scenario E — Persistence

Validates FR-008 and SC-004.

1. In Scenario A or B, after the evaluation cell completes, run the optional persistence cell with `OUT_DIR` left at its default (`evaluation_runs/vector_only/<run_id>/`).
2. **Expected outcome**:
   - `retrieval_cases.jsonl` and `retrieval_metrics.json` are written under the run-scoped directory, matching the shapes in [`contracts/notebook-io-contract.md`](./contracts/notebook-io-contract.md:1).
   - Both files can be independently re-loaded, e.g.:
     ```python
     import json
     from pathlib import Path
     out_dir = Path("evaluation_runs/vector_only/<run_id>")
     cases = [json.loads(line) for line in (out_dir / "retrieval_cases.jsonl").read_text().splitlines()]
     metrics = json.loads((out_dir / "retrieval_metrics.json").read_text())
     assert cases and metrics["overall"]["count"] == len(cases)
     ```

## Cleanup

- Smoke-test and experimentation runs do not require cleanup (in-memory only).
- If Scenario E was run repeatedly, remove stale `evaluation_runs/vector_only/<run_id>/` directories you no longer need (each run uses a fresh timestamped `run_id`, so old runs are never overwritten).
