# Remote BM25 Retrieval Integration

## Summary

The main repository supports remote BM25 retrieval alongside Dense retrieval. In the production Streamlit path, `Agent-None-RemoteDense` is selected with Dense-Sparse enabled by default: the UI calls `answer_question`, the QA service builds a remote Dense retriever plus remote BM25 retriever, `HybridRetriever` executes both branches concurrently, weighted RRF merges candidates, and the existing E2E generation/citation flow consumes the fused `RetrievedChunk` list.

The standalone BM25 backend remains available for evaluation and compatibility, but the production UI default is remote Dense plus remote BM25 with `filter_profile=current_law`.

## Components

| File | Purpose |
| --- | --- |
| `src/retrieval/bm25_client.py` | Dependency-free HTTP client for the remote BM25 service. |
| `src/retrieval/bm25_retriever.py` | Adapter that maps remote BM25 hits into the local retrieval interface. |
| `src/retrieval/__init__.py` | Exports BM25 client and retriever classes. |
| `src/retrieval/hybrid_retriever.py` | Runs Dense and BM25 concurrently and applies weighted RRF. |
| `src/service/qa_service.py` | Applies UI overrides, validates readiness, constructs production resources, and passes `filter_profile` into retrieval. |
| `ui/app.py` | Defaults production retrieval to Dense-Sparse and exposes the filter profile control. |
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
    "filter_profile": "current_law",
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
  "shard_name": "shard_00",
  "shard_rank": 1
}
```

The remote BM25 service returns IDs and sparse scores by default. It keeps all resident BM25 index objects in memory, stores only lightweight chunk-id maps, and hydrates final payloads lazily from `payload_cache.sqlite` when payloads or `current_law`/`historical` filtering are required. It must not deserialize `bm25_metadata.pkl` during normal query execution after chunk-id maps exist.

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

Production hybrid values are configured in `configs/ablation_configs.yaml` under `Agent-None-RemoteDense`:

```yaml
retrieval:
  filter_profile: current_law
  sparse:
    enabled: true
    backend: bm25_remote
    rrf_k: 60
    dense_weight: 1.0
    bm25_weight: 0.3
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

## Production Retrieval Flow

1. `ui/app.py` sends `QuestionRequest(filter_profile="current_law", sparse_enabled_override=True)`.
2. `src/service/qa_service.py` applies overrides and calls `run_e2e_evaluation` with the effective filter profile.
3. `scripts/run_ablation_config.py::build_ablation_stack` constructs remote Dense and remote BM25 clients, then wraps them in `HybridRetriever`.
4. `HybridRetriever.retrieve_with_latency` uses a bounded `ThreadPoolExecutor(max_workers=2)` to invoke Dense and BM25 in parallel.
5. Dense receives the same `filter_profile`; BM25 receives it in the `/bm25` JSON body.
6. Weighted RRF merges rankings with `rrf_k=60`, `dense_weight=1.0`, and `bm25_weight=0.3`.
7. Fused hits are converted to `RetrievedChunk`, preserving chunk text, citation fields, document ids, scores, and metadata for generation/citations.

BM25 score is stored in `RetrievedChunk.vector_score` and `RetrievedChunk.rerank_score` for compatibility with downstream code that already expects those fields.

## Operational Requirements

- The remote BM25 index and the local FAISS/Qdrant payload store must be built from the same corpus snapshot.
- BM25 hits whose `chunk_id` cannot be hydrated are skipped by the retriever or filtered out by the BM25 service when a law filter requires payload metadata.
- The BM25 service should use `BM25_PAYLOAD_CACHE_PATH=/workspace/artifacts/dense/payload_cache.sqlite` on RunPod so current-law filtering does not reload metadata pickles.
- `BM25_SEARCH_WORKERS` controls bounded parallel search inside the resident BM25 service; `4` is the current service default.
- `expand_units` is accepted for interface compatibility but is not currently applied by the BM25 adapter.
- Vector-specific reranking and same-unit expansion remain part of the vector path only.
- The factory function name `build_vector_retriever()` was preserved for compatibility even though it can now return either a vector or BM25 retriever.

## Validation

Run the focused checks from a repo environment with the project dependencies installed:

```powershell
python -m py_compile ui/app.py src/service/qa_service.py src/service/ui_runtime.py src/retrieval/hybrid_retriever.py src/retrieval/bm25_client.py src/retrieval/bm25_retriever.py src/retrieval/sparse_retriever.py services/bm25_service.py scripts/run_ablation_config.py
python -m pytest tests/services/test_bm25_service.py tests/retrieval/test_bm25_client.py tests/retrieval/test_bm25_retriever.py tests/retrieval/test_hybrid_retriever.py tests/ui/test_ui_service.py tests/ui/test_ui_production_readiness.py tests/evaluation/test_evaluation_retriever_factory.py tests/ablation/test_ablation_config.py -q
```

