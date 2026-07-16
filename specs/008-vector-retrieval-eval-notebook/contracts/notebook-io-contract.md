# Contract: Vector-Only Retrieval Evaluation Notebook — I/O Shapes

This is not a library/API surface; the notebook has no external callers other than the person running it. This document fixes the on-disk artifact contract (FR-008) so downstream reporting tools can rely on it, per SC-004.

## Inputs

| Input | Format | Contract |
|---|---|---|
| `data/qa_final.jsonl` | JSONL | One QA object per line: `qa_id?`, `question`, `answer_type`, `category`, `difficulty`, `ground_truth.{chunk_ids,document_ids,provision_ids}`. Read-only; never written to by this notebook (FR-009 also implies nothing here writes into `data/`). |
| Local FAISS index directory | Filesystem (`INDEX_DIR`, default `data/faiss_index/`) | Must contain `index.faiss` and `payloads.jsonl`; `payload_cache.sqlite` is built/refreshed automatically on load if missing or stale. Loaded via [`SQLitePayloadFaissVectorStore.load(index_dir)`](../../../src/retrieval/sqlite_faiss_store.py:289), which raises `FileNotFoundError` naming the missing file if `index.faiss` or `payloads.jsonl` is absent. **Qdrant is not used by this notebook.** |

## Outputs (only when persistence is triggered — FR-008 is optional per run)

### `retrieval_cases.jsonl`

One JSON object per line, one line per evaluated (eligible) case, produced by [`write_case_jsonl`](../../../src/evaluation/retrieval_eval_report.py:178):

```json
{
  "qa_id": "qa-000123",
  "mode": "vector_only",
  "question": "...",
  "category": "...",
  "difficulty": "...",
  "answer_type": "...",
  "ground_truth_chunk_ids": ["c1", "c2"],
  "retrieved_chunk_ids": ["c2", "c9", "c1"],
  "error": null,
  "recall@1": 0.0,
  "hit@1": 0.0,
  "mrr@1": 0.0,
  "ndcg@1": 0.0,
  "jaccard@1": 0.0,
  "recall@5": 1.0,
  "hit@5": 1.0,
  "mrr@5": 0.5,
  "ndcg@5": 0.63,
  "jaccard@5": 0.4
}
```

`hybrid_diagnostics` key is always omitted (only present when non-`None`, and this notebook never sets it, per [`_case_result_to_dict`](../../../src/evaluation/retrieval_eval_report.py:145)).

### `retrieval_metrics.json`

Single JSON object, produced by [`write_metrics_json`](../../../src/evaluation/retrieval_eval_report.py:184):

```json
{
  "mode": "vector_only",
  "config": {
    "index_dir": "data/faiss_index",
    "model": "intfloat/multilingual-e5-large",
    "score_threshold": 0.3,
    "expand_units": true,
    "top_k": [1, 5, 10],
    "sample_limit": null
  },
  "counts": {
    "total_rows": 500,
    "evaluated": 420,
    "skipped_unanswerable": 50,
    "skipped_missing_ground_truth": 30,
    "error_count": 0
  },
  "overall": { "recall@1": 0.0, "hit@1": 0.0, "...": "..." },
  "by_category": { "contract": { "count": 120, "recall@1": 0.0, "...": "..." } },
  "by_difficulty": { "easy": { "count": 200, "...": "..." } },
  "by_answer_type": { "extractive": { "count": 300, "...": "..." } }
}
```

## Error contract

| Condition | Required behavior | FR |
|---|---|---|
| `QA_PATH` missing/unreadable | Raise a clear error naming the expected path before any retrieval cell runs (e.g., `FileNotFoundError(f"qa_final.jsonl not found at {QA_PATH}")`) | FR-011 |
| `INDEX_DIR` missing / `index.faiss` or `payloads.jsonl` absent / SQLite payload cache unreadable or corrupt | Raise a clear load/configuration error at the retrieval step (not swallowed into empty results) — surfaced by [`SQLitePayloadFaissVectorStore.load`](../../../src/retrieval/sqlite_faiss_store.py:289)'s `FileNotFoundError` or a caught cache-read exception | FR-012 |
| Zero eligible cases | Display counts (`total_rows`, `skipped_unanswerable`, `skipped_missing_ground_truth`, `evaluated=0`) and a zero-count aggregate table; no exception | FR-013 |
| Invalid `top_k` vs retrieved length | No special handling; `metrics.py` slicing semantics apply unchanged | Edge case in spec |

## Non-goals (explicitly out of contract)

- No knowledge-graph, `GraphExpansion`, `GraphTraversal`, or hybrid-fusion object appears in any input, output, or intermediate notebook variable (FR-002).
- No import from or read of any file under `L_RAG/notebooks/archive/` (FR-009).
