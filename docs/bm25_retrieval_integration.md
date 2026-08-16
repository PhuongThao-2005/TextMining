# Remote BM25 Retrieval Integration

## Summary

The main repository now supports a remote BM25 retrieval backend alongside the existing vector retrieval backend. The BM25 path calls an external BM25 service, receives ranked `chunk_id` hits, hydrates those hits from the local FAISS or Qdrant payload store, and returns the existing `RetrievalResult` / `RetrievedChunk` contract used by retrieval and E2E evaluation.

Default behavior remains unchanged: `backend="vector"` is still used unless BM25 is selected explicitly.

## Components

| File | Purpose |
| --- | --- |
| `src/retrieval/bm25_client.py` | Dependency-free HTTP client for the remote BM25 service. |
| `src/retrieval/bm25_retriever.py` | Adapter that maps remote BM25 hits into the local retrieval interface. |
| `src/retrieval/__init__.py` | Exports BM25 client and retriever classes. |
| `src/evaluation/retriever_factory.py` | Selects either vector or BM25 retrieval based on runtime config. |
| `scripts/evaluate_retrieval.py` | Adds BM25 CLI options for retrieval-only evaluation. |
| `scripts/evaluate_e2e.py` | Adds BM25 CLI options for end-to-end evaluation. |
| `tests/retrieval/test_bm25_retriever.py` | Covers BM25 hit hydration and ranking preservation. |
| `tests/test_evaluation_retriever_factory.py` | Covers factory wiring for the BM25 backend. |

## Remote Service Contract

The client calls the remote service with `POST /bm25` using the RunPod-compatible envelope:

```json
{
  "input": {
    "queries": [
      {
        "qa_id": "question-id",
        "question": "query text"
      }
    ],
    "bm25_top_k": 10,
    "include_diagnostics": false
  }
}
```

Expected hits include at least:

```json
{
  "chunk_id": "chunk-id",
  "bm25_score": 12.34,
  "rank": 1,
  "shard_id": 0,
  "local_index": 123
}
```

The remote BM25 service returns IDs and sparse scores only. Full chunk text, citations, document IDs, and metadata are loaded from the configured local payload store.

## Runtime Configuration

`RetrieverRuntimeConfig` supports these BM25-related fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `backend` | `"vector"` | Selects `"vector"` or `"bm25"`. |
| `store` | existing default | Selects the local payload/index store, usually `faiss` or `qdrant`. |
| `index_dir` | existing default | Local index directory used for payload hydration. |
| `bm25_service_url` | `BM25_SERVICE_URL` | Base URL for the remote BM25 service. |
| `bm25_api_key` | `BM25_API_KEY` | Optional bearer token for the remote service. |
| `bm25_timeout_seconds` | client default | HTTP timeout for BM25 requests. |

When `BM25_API_KEY` is present, the client sends:

```http
Authorization: Bearer <BM25_API_KEY>
```

## CLI Usage

Retrieval-only evaluation:

```powershell
Set-Location D:\Uni_Project\Text_Mining\Project
$env:BM25_SERVICE_URL = "https://your-bm25-service"

D:\Uni_Project\Text_Mining\env\python.exe scripts\evaluate_retrieval.py `
  --qa-path data\benchmark\qa_final.jsonl `
  --retriever-backend bm25 `
  --store faiss `
  --index-dir data\indexes\faiss
```

End-to-end evaluation:

```powershell
Set-Location D:\Uni_Project\Text_Mining\Project
$env:BM25_SERVICE_URL = "https://your-bm25-service"

D:\Uni_Project\Text_Mining\env\python.exe scripts\evaluate_e2e.py `
  --qa-path data\benchmark\qa_final.jsonl `
  --retriever-backend bm25 `
  --store faiss `
  --index-dir data\indexes\faiss
```

The same values can be passed explicitly with `--bm25-service-url`, `--bm25-api-key`, and `--bm25-timeout-seconds`.

## Retrieval Flow

1. The evaluation script builds `RetrieverRuntimeConfig` with `backend="bm25"`.
2. `build_vector_retriever()` creates a `BM25RemoteRetriever` instead of the vector retriever.
3. `BM25RemoteRetriever` sends the query to the remote BM25 service.
4. Returned `chunk_id` values are hydrated through the local payload store using the existing chunk metadata.
5. Filter profiles and graph-guided filters are applied during hydration.
6. Results are returned through the existing retrieval schema, preserving BM25 ranking order.

BM25 score is stored in `RetrievedChunk.vector_score` and `RetrievedChunk.rerank_score` for compatibility with downstream code that already expects those fields.

## Operational Requirements

- The remote BM25 index and the local FAISS/Qdrant payload store must be built from the same corpus snapshot.
- BM25 hits whose `chunk_id` cannot be found in the local payload store are skipped.
- `expand_units` is accepted for interface compatibility but is not currently applied by the BM25 adapter.
- Vector-specific reranking and same-unit expansion remain part of the vector path only.
- The factory function name `build_vector_retriever()` was preserved for compatibility even though it can now return either a vector or BM25 retriever.

## Validation

The changed Python modules compile successfully with `py_compile`. A manual smoke test confirmed that remote BM25 hit order is preserved after local payload hydration.

The focused pytest tests were added but could not be executed in the available environment because `pytest` is not installed. Run them from an environment with pytest available:

```powershell
Set-Location D:\Uni_Project\Text_Mining\Project
D:\Uni_Project\Text_Mining\env\python.exe -m pytest tests\retrieval\test_bm25_retriever.py tests\test_evaluation_retriever_factory.py -q
```

