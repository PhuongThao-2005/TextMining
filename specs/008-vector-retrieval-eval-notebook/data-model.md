# Phase 1 Data Model: Vector-Only Retrieval Evaluation Notebook

All entities below are already defined by existing, tested modules under `src/evaluation/` and `src/retrieval/`. This document maps the spec's Key Entities to those concrete types and states what (if anything) the notebook adds on top.

## 1. QA benchmark row

- **Source**: A single line of `data/qa_final.jsonl`, read via [`read_jsonl()`](../../../src/evaluation/io_utils.py:8).
- **Shape** (raw `dict`): `qa_id` (optional; falls back to `id` or a generated `qa-{index:06d}` via [`qa_id()`](../../../src/evaluation/io_utils.py:32)), `question`, `answer_type`, `category`, `difficulty`, `ground_truth` (`chunk_ids: list[str]`, `provision_ids: list[str]`, `document_ids: list[str]`).
- **Notebook role**: Input only, never mutated. Iterated once per notebook run.

## 2. Eligible case

- **Type**: [`EligibleCase`](../../../src/evaluation/eligibility.py:14) (frozen dataclass): `qa_id`, `question`, `category`, `difficulty`, `answer_type`, `ground_truth_chunk_ids: set[str]`, `ground_truth_document_ids: set[str]`, `ground_truth_provision_ids: set[str]`, `raw_row: dict`.
- **Produced by**: [`select_eligible_cases(rows, sample_limit)`](../../../src/evaluation/eligibility.py:48), returning an [`EligibilitySummary`](../../../src/evaluation/eligibility.py:29): `total_rows`, `eligible: list[EligibleCase]`, `skipped_unanswerable`, `skipped_missing_ground_truth`.
- **Notebook role**: Directly consumed to drive the retrieval loop (FR-003). No new fields added.

## 3. Vector-only retrieval result

- **Type**: [`RetrievalResult`](../../../src/retrieval/schema.py:30) (`chunks: list[RetrievedChunk]`, `total_candidates`, `filter_profile_used`, `empty_filter_warning`), where each [`RetrievedChunk`](../../../src/retrieval/schema.py:11) carries `chunk_id`, `chunk_text`, `citation_anchor`, `citation_label`, `title`, `article_number`, `unit_type`, `path`, `validity_group`, `legal_authority_rank`, `vector_score`, `rerank_score`, `id_str`, `parent_unit_id`, `metadata`.
- **Produced by**: [`VectorRetriever.retrieve(...)`](../../../src/retrieval/retriever.py:31), constructed via [`build_vector_retriever(RetrieverRuntimeConfig(...))`](../../../src/evaluation/retriever_factory.py:22) — per the clarification correction, this notebook uses the FAISS + SQLite payload-cache path (`store="faiss"`, backed by [`SQLitePayloadFaissVectorStore.load(index_dir)`](../../../src/retrieval/sqlite_faiss_store.py:289)), not Qdrant. FR-002a tracks the required extension to `retriever_factory.py`.
- **Notebook role**: For each eligible case, call `retriever.retrieve(question, filter_profile=..., top_n=max(top_k_list))`; extract `retrieved_chunk_ids = [c.chunk_id for c in result.chunks]`. No new fields added; the notebook does not need `filter_profile_used`/`empty_filter_warning` for scoring but MAY surface them in per-case diagnostics for User Story 3's troubleshooting needs.

## 4. Per-case metrics row

- **Type**: [`RetrievalCaseResult`](../../../src/evaluation/retrieval_eval_report.py:41) (frozen dataclass): `qa_id`, `mode` (`"vector_only"`), `question`, `category`, `difficulty`, `answer_type`, `ground_truth_chunk_ids: list[str]`, `retrieved_chunk_ids: list[str]`, `metrics: dict[str, float]`, `hybrid_diagnostics: None` (always `None` for this notebook — vector-only never populates this field), `error: str | None`.
- **Metrics populated by**: [`build_case_metrics_row(retrieved_chunk_ids, ground_truth_chunk_ids, top_k_list)`](../../../src/evaluation/retrieval_eval_report.py:94), which calls `recall_at_k`/`hit_at_k`/`mrr_at_k`/`ndcg_at_k`/`jaccard_at_k` from [`metrics.py`](../../../src/evaluation/metrics.py:71) for every configured `k` — the sole metric source (FR-004).
- **Serialization**: [`write_case_jsonl(path, cases)`](../../../src/evaluation/retrieval_eval_report.py:178) → one JSON object per line via `_case_result_to_dict`, satisfying FR-008's per-case JSONL shape (`qa_id`, question, ground-truth/retrieved chunk IDs, per-k metrics).

## 5. Run summary

- **Type**: [`ModeRunSummary`](../../../src/evaluation/retrieval_eval_report.py:58): `mode`, `config: dict`, `total_rows`, `evaluated`, `skipped_unanswerable`, `skipped_missing_ground_truth`, `error_count`, `overall: dict`, `by_category: dict`, `by_difficulty: dict`, `by_answer_type: dict`, `hybrid_available` (always `True`/unused meaning for vector-only — set to `True` with `hybrid_unavailable_reason=None` since hybrid concepts don't apply), computed from:
  - `overall = aggregate(case_dicts, metric_keys)` — [`aggregate()`](../../../src/evaluation/metrics.py:110)
  - `by_category = aggregate_by(case_dicts, "category", metric_keys)`, similarly for `difficulty`/`answer_type` — [`aggregate_by()`](../../../src/evaluation/metrics.py:118)
- **Serialization**: [`write_metrics_json(path, summary, run_config)`](../../../src/evaluation/retrieval_eval_report.py:184), satisfying FR-008's aggregate metrics JSON shape (counts, overall, by_category, by_difficulty, by_answer_type).
- **Notebook-only fields (not persisted, session-display only)**: `run_id` (timestamp string), `qa_path` (resolved `Path`), `output_dir` (resolved `Path`, only meaningful if persistence is triggered). These are notebook-local variables, not part of any `src/` dataclass, and exist purely to drive FR-006/FR-007/FR-010's configuration-and-labeling display.

## 6. Notebook Configuration (new, notebook-local only)

Not a `src/` dataclass — a plain set of variables in the notebook's marked configuration cell, mapping 1:1 onto [`RetrieverRuntimeConfig`](../../../src/evaluation/retriever_factory.py:8) plus benchmark/run controls. Per the clarification correction, this notebook is FAISS + SQLite-backed, not Qdrant, so the config surface exposes `INDEX_DIR` instead of any Qdrant connection settings:

| Variable | Maps to | Default | Notes |
|---|---|---|---|
| `QA_PATH` | n/a (notebook input path) | `data/qa_final.jsonl` (resolved from project root) | FR-011 guard: existence checked before use |
| `TOP_K_LIST` | derives `RetrieverRuntimeConfig.top_n`/sizing | `[1, 5, 10]` | FR-006 |
| `INDEX_DIR` | `RetrieverRuntimeConfig.index_dir` (new field, FR-002a) | `data/faiss_index/` | FR-006; directory must contain `index.faiss` + `payloads.jsonl`; `payload_cache.sqlite` is auto-built/refreshed by [`SQLitePayloadFaissVectorStore.load(index_dir)`](../../../src/retrieval/sqlite_faiss_store.py:289). Qdrant is not used by this notebook. |
| `MODEL_NAME` | `RetrieverRuntimeConfig.model` | `intfloat/multilingual-e5-large` | FR-006 |
| `SCORE_THRESHOLD` | `RetrieverRuntimeConfig.score_threshold` | `0.3` | FR-006 |
| `EXPAND_UNITS` | `RetrieverRuntimeConfig.expand_units` | `True` | FR-006 |
| `SAMPLE_LIMIT` | `select_eligible_cases(..., sample_limit=...)` | `None` | FR-006, US2 scenario 3 |
| `DEV_HASHING` | `RetrieverRuntimeConfig.dev_hashing` | `False` | Enables smoke-test path (Independent Test in US1) without a populated FAISS index/model |
| `OUT_DIR` | notebook-local, base for `write_case_jsonl`/`write_metrics_json` paths | `evaluation_runs/vector_only/<run_id>/` | FR-008; only used if persistence is triggered |

## Validation rules (from spec Functional Requirements)

- Every QA row → exactly one of eligible / skipped_unanswerable / skipped_missing_ground_truth (FR-003; enforced entirely by `select_eligible_cases`, not re-validated in the notebook).
- `top_k` values are used as-is by `metrics.py` functions even when `k > len(retrieved_ids)` (FR handled via existing `recall_at_k`/etc. semantics — slicing `retrieved_ids[:k]` naturally saturates at list length).
- Re-running retrieval/evaluation cells after a config change must not merge stale per-case rows into the new run (FR-014): the notebook's per-run `case_dicts`/`cases` list MUST be freshly re-initialized (e.g., `cases = []`) at the top of the retrieval cell on every execution, never appended to across reruns.
- Zero eligible cases (FR-013): `aggregate([], metric_keys)` already returns `{"count": 0, **{k: 0.0 for k in metric_keys}}` per [`aggregate()`](../../../src/evaluation/metrics.py:110) — no special-casing needed in the notebook beyond displaying the resulting zero-count summary clearly.

## State transitions

None — this is a stateless, single-pass evaluation flow per run (load → filter → retrieve → score → aggregate → display → optional persist). No entity here has a lifecycle beyond one notebook execution.
