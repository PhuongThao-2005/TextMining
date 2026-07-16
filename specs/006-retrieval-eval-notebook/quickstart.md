# Quickstart: Retrieval Evaluation Notebook

## Prerequisites

- Python env with project deps installed (`pyproject.toml`), FAISS/sentence-transformers available for real (non-hashing) embeddings.
- FAISS index artifacts under an `INDEX_DIR` (e.g. `data/faiss_index/`): `payloads.jsonl` (+ auto-built `payload_cache.sqlite`), FAISS index files matching the configured `EMBEDDING_MODEL`.
- Frozen benchmark at `data/benchmark/qa_final.jsonl` (default path). If your checkout only has `data/qa_final.jsonl`, either copy/symlink it to `data/benchmark/qa_final.jsonl` or set `QA_PATH` explicitly in the config cell — the notebook prints one explicit warning and uses `data/qa_final.jsonl` only when the default path is missing **and** you have not overridden `QA_PATH` ([`research.md`](./research.md) R10).
- For hybrid evaluation: a structural graph pickle at `data/graph/knowledge_graph.gpickle` (features 004/005). JSONL rebuild is available but opt-in (`ALLOW_JSONL_GRAPH_REBUILD=True`) and heavier. Overlays are optional.

### Expected inputs (preflight)

| Artifact | Required for | Preflight behavior when missing |
| --- | --- | --- |
| `QA_PATH` | vector-only, hybrid | Stop with clear error before any retrieval (Edge Cases) |
| `INDEX_DIR` (`payloads.jsonl`, FAISS index) | vector-only, hybrid | Stop with clear error; no partial run |
| `GRAPH_PICKLE_PATH` or JSONL rebuild opt-in | hybrid only | `hybrid_available=False`, vector-only still runs (FR-011) |
| Overlays (`authority_index.jsonl`, `validity_timeline.jsonl`) | hybrid (optional) | Explicit "overlays unavailable" diagnostic; hybrid still counts as full hybrid if Traversal+Expansion succeed (research R9) |

## Setup (once)

```bash
cd L_RAG
pytest tests/test_evaluation_metrics.py tests/test_evaluation_eligibility.py \
       tests/test_evaluation_hybrid_fusion.py tests/test_evaluation_retrieval_eval_report.py -q
# Existing evaluation/retrieval/knowledge_graph suites still pass (no required changes to them)
```

## Config cell (near top of `notebooks/retrieval_eval.ipynb`)

```python
QA_PATH = "data/benchmark/qa_final.jsonl"   # override if your checkout uses data/qa_final.jsonl
OUT_DIR = "evaluation_runs/retrieval_notebook/run1"
TOP_K_LIST = [1, 5, 10]
SAMPLE_LIMIT = 20          # None for full benchmark

FILTER_PROFILE = "current_law"
SCORE_THRESHOLD = None
TOP_K_RETRIEVE = 20
TOP_N = 10

INDEX_DIR = "data/faiss_index"
EMBEDDING_MODEL = "<model matching the built index>"

RUN_VECTOR_ONLY = True
RUN_HYBRID = True

GRAPH_PICKLE_PATH = "data/graph/knowledge_graph.gpickle"
V2_DATA_DIR = "data/v2"
ALLOW_JSONL_GRAPH_REBUILD = False

TRAVERSAL_MODE = "basis"
TRAVERSAL_MAX_DEPTH = 3
PREPASS_TOP_N = 10
MAX_TRAVERSAL_STARTS = 5

HYBRID_MAX_HOP = 2
HYBRID_MAX_CONTEXT = 20

AS_OF_DATE = None
LOCAL_EXPAND_UNITS = False   # keep False for official scored hybrid
```

## Recommended run order

1. Run the config + preflight cells; confirm QA path, FAISS artifacts, and graph source are resolved (or hybrid marked unavailable).
2. Run the vector-only evaluation cell (US1). Inspect eligible/skipped counts and per-k overall metrics.
3. Run the hybrid evaluation cell (US2), only if hybrid preflight passed. Inspect traversal/whitelist/expansion diagnostics per case.
4. Run the comparison cell (US3) once both modes have completed.
5. Confirm artifacts were written under `OUT_DIR` (US4).

## Validation scenarios

### V1 — Vector-only happy path (US1, SC-001, SC-003, SC-006)

Given valid `QA_PATH` and `INDEX_DIR`, run the vector-only cell with `SAMPLE_LIMIT=20`. Expect: 20 (or fewer, if eligible pool is smaller) eligible cases scored via [`src/evaluation/metrics.py`](../../src/evaluation/metrics.py) at every configured k, `skipped_unanswerable`/`skipped_missing_ground_truth` counters shown separately from evaluated count, and `vector_only_cases.jsonl` / `vector_only_metrics.json` / `vector_only_report.md` written.

### V2 — Hybrid happy path, both graph services present (US2, SC-002)

With `GRAPH_PICKLE_PATH` resolvable, run the hybrid cell. Expect: every case labeled `mode=hybrid`, `hybrid_diagnostics` showing non-null `traversal_start_ids` derived from the unfiltered pre-pass (never `ground_truth.*`), a whitelist/visited-id summary, and expansion counts (possibly zero-added, which is not an error). Fused `retrieved_chunk_ids` order is seeds → expansion → extra traversal chunks, deduped keep-first ([`data-model.md`](./data-model.md) §2.7).

### V3 — Dual-mode comparison (US3, SC-004)

After V1 and V2 complete on the same `SAMPLE_LIMIT`, run the comparison cell. Expect a table with one row per `metric@k` and columns for `vector_only` / `hybrid`, plus separate evaluated/skipped counts per mode.

### V4 — Hybrid unavailable, vector-only still runs (US2 AC3, US3 AC3, FR-011, SC-007)

Point `GRAPH_PICKLE_PATH` at a non-existent file with `ALLOW_JSONL_GRAPH_REBUILD=False`. Expect: hybrid cell reports `hybrid_available=False` with an explicit reason (e.g. `graph_unavailable`); vector-only cell still completes normally; comparison cell shows vector-only metrics and an explicit "hybrid unavailable" note — never a hybrid-labeled table built from vector-only numbers.

### V5 — Empty ground truth / unanswerable rows never scored (US1 AC3, SC-006)

Include or rely on existing benchmark rows with empty `ground_truth.chunk_ids` or unanswerable `answer_type`/`category`. Expect they increment `skipped_missing_ground_truth` / `skipped_unanswerable` and never appear as a scored 0 or 1 in aggregate metrics.

### V6 — Empty traversal pre-pass starts (Edge Cases, FR-003g)

Simulate or find a question whose unfiltered vector pre-pass returns no usable start mapping. Expect: that case's `hybrid_diagnostics.prepass_empty_start=True`, no substitution of `ground_truth` IDs, and the case is either scored on a legitimate remaining path or marked failed for that case — run does not silently widen to full-corpus search under a hybrid label.

### V7 — Per-case retrieval error does not abort the run (FR-015)

Force or observe a single case retrieval exception (e.g. transient index issue). Expect: that case is recorded with `error` set (or counted in `error_count`) and the run continues to completion for remaining cases.

### V8 — Path portability (FR-016)

Run the notebook from both the project root and from inside `notebooks/`. Expect identical path resolution behavior for `QA_PATH`, `INDEX_DIR`, `GRAPH_PICKLE_PATH`, and `OUT_DIR` without editing hardcoded absolute paths.

## Out of scope checks (do not require for acceptance)

- No exact-match / token-F1 / ROUGE-L / judge-score generation metrics anywhere in this notebook (FR-018).
- No modification of `data/benchmark/qa_final.jsonl` under any run (FR-017).
- No changes to `scripts/evaluate_retrieval.py`, `scripts/evaluate_e2e.py`, or `src/evaluation/retriever_factory.py`'s Qdrant-only contract.
