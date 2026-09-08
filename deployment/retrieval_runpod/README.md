# Retrieval RunPod Deployment

This deployment runs two separate services in one RunPod Pod:

```text
Dense service :8000  -> services.dense_service
BM25 service  :8001  -> services.bm25_service
```

They are colocated for cost and deployment convenience only. The APIs, clients,
retrieval logic, environment variables, and ports remain separate, so the two
services can later move to different Pods by changing `DENSE_SERVICE_URL` and
`BM25_SERVICE_URL`.

## Artifact Layout

Mount persistent storage so Dense artifacts are at `/workspace/artifacts/dense`
and the existing BM25 artifacts stay visible at
`/workspace/bm25_service/bm25/shards`:

```text
/workspace/artifacts/
├── dense/
│   ├── index.faiss
│   ├── payloads.jsonl
│   ├── payload_cache.sqlite      # recommended; rebuilt if absent and writable
│   ├── index_manifest.json
│   └── id_map.json               # optional; used only if present
└── cache/
    ├── huggingface/
    ├── sentence-transformers/
    └── torch/

/workspace/bm25_service/bm25/shards/
├── shard_00/
│   ├── bm25_index.pkl
│   ├── bm25_metadata.pkl
│   └── manifest.json
├── ...
└── shard_09/
    ├── bm25_index.pkl
    ├── bm25_metadata.pkl
    └── manifest.json
```

Large artifacts, model cache, and secrets are not baked into the Docker image.
Do not rebuild, merge, move, duplicate, or copy the existing BM25 shard data
into `/workspace/artifacts/bm25`.

## Required Environment

```text
DENSE_INDEX_DIR=/workspace/artifacts/dense
DENSE_SERVICE_URL=https://YOUR_DENSE_URL
DENSE_API_KEY=replace-with-secret
DENSE_MODEL=intfloat/multilingual-e5-large
DENSE_EXPECTED_MODEL=intfloat/multilingual-e5-large
DENSE_EXPECTED_INDEX_VERSION=chunk-metadata-faiss-v1
DENSE_TIMEOUT_SECONDS=30
DENSE_DEVICE=cuda

BM25_INDEX_DIR=/workspace/bm25_service/bm25/shards
BM25_SERVICE_URL=https://YOUR_BM25_URL
BM25_API_KEY=replace-with-secret
BM25_INDEX_VERSION=lexvn-bm25-v1
BM25_PAYLOAD_CACHE_PATH=/workspace/artifacts/dense/payload_cache.sqlite
BM25_SEARCH_WORKERS=4

HF_HOME=/workspace/artifacts/cache/huggingface
SENTENCE_TRANSFORMERS_HOME=/workspace/artifacts/cache/sentence-transformers
TORCH_HOME=/workspace/artifacts/cache/torch
```

Use internal/local URLs if the UI runs in the same private network. Use RunPod
proxy URLs only after the Pod exposes ports `8000` and `8001`.

## Prepare Artifacts Locally

Dense artifacts are the existing FAISS bundle:

```powershell
Test-Path "data/chunk metadata/index.faiss"
Test-Path "data/chunk metadata/payloads.jsonl"
Test-Path "data/chunk metadata/index_manifest.json"
```

BM25 artifacts already exist on the RunPod Network Volume. Do not rebuild or
copy them for production. For local development only, a single-index
`data/sparse_index` layout remains supported:

```powershell
D:\anaconda3\python.exe scripts\build_sparse_index.py --chunks-path data\pre-processed\chunks.jsonl --output-dir data\sparse_index
```

## Upload Data

Do not upload `.env` or API keys.

If the Pod has SSH enabled, copy only Dense artifacts into the mounted volume:

```powershell
$Pod = "root@YOUR_POD_HOST"
scp "data/chunk metadata/index.faiss" "${Pod}:/workspace/artifacts/dense/"
scp "data/chunk metadata/payloads.jsonl" "${Pod}:/workspace/artifacts/dense/"
scp "data/chunk metadata/payload_cache.sqlite" "${Pod}:/workspace/artifacts/dense/"
scp "data/chunk metadata/index_manifest.json" "${Pod}:/workspace/artifacts/dense/"
scp "data/chunk metadata/id_map.json" "${Pod}:/workspace/artifacts/dense/"
```

If using object storage, upload from local and sync from the Pod:

```bash
aws s3 sync "data/chunk metadata" "s3://YOUR_BUCKET/lexvn/dense"
aws s3 sync "s3://YOUR_BUCKET/lexvn/dense" "/workspace/artifacts/dense"
```

Keep the Dense FAISS bundle and existing BM25 shards from the same corpus snapshot.

## Local Service Test

Dense:

```powershell
$env:DENSE_INDEX_DIR = "data/chunk metadata"
$env:DENSE_EXPECTED_MODEL = "intfloat/multilingual-e5-large"
$env:DENSE_EXPECTED_INDEX_VERSION = "chunk-metadata-faiss-v1"
$env:DENSE_API_KEY = "local-secret"
D:\anaconda3\python.exe -m uvicorn services.dense_service:app --host 127.0.0.1 --port 8000
```

BM25:

```powershell
$env:BM25_INDEX_DIR = "data/sparse_index"
$env:BM25_API_KEY = "local-secret"
$env:BM25_PAYLOAD_CACHE_PATH = "data/chunk metadata/payload_cache.sqlite"
$env:BM25_SEARCH_WORKERS = "4"
D:\anaconda3\python.exe -m uvicorn services.bm25_service:app --host 127.0.0.1 --port 8001
```

Probe:

```powershell
curl -H "Authorization: Bearer local-secret" http://127.0.0.1:8000/healthz
curl -H "Authorization: Bearer local-secret" http://127.0.0.1:8000/readyz
curl -H "Authorization: Bearer local-secret" http://127.0.0.1:8000/version
curl -H "Authorization: Bearer local-secret" http://127.0.0.1:8001/healthz
```

Dense search:

```powershell
curl -X POST http://127.0.0.1:8000/search `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer local-secret" `
  -d "{\"query\":\"Người lao động được nghỉ hằng năm bao nhiêu ngày?\",\"top_k\":30,\"top_n\":5,\"filter_profile\":\"broad\",\"request_id\":\"local-smoke\"}"
```

BM25 search:

```powershell
curl -X POST http://127.0.0.1:8001/bm25 `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer local-secret" `
  -d "{\"input\":{\"queries\":[{\"qa_id\":\"q1\",\"question\":\"người lao động nghỉ hằng năm\"}],\"bm25_top_k\":5,\"filter_profile\":\"current_law\",\"include_payloads\":true,\"include_diagnostics\":true}}"
```

UI against both remote clients:

```powershell
$env:DENSE_SERVICE_URL = "http://127.0.0.1:8000"
$env:DENSE_API_KEY = "local-secret"
$env:BM25_SERVICE_URL = "http://127.0.0.1:8001"
$env:BM25_API_KEY = "local-secret"
D:\anaconda3\python.exe -m streamlit run ui/app.py --server.headless true --server.port 8501
```

Select `Agent-None-RemoteDense` in the UI config selector. Production defaults to Dense-Sparse retrieval with `filter_profile=current_law`; Dense calls `/readyz`, BM25 calls `/healthz`, and a normal question invokes both remote services concurrently before weighted RRF fusion.

## Parity Test

Compare local FAISS Dense retrieval against the remote Dense service:

```powershell
$env:DENSE_SERVICE_URL = "http://127.0.0.1:8000"
$env:DENSE_API_KEY = "local-secret"
D:\anaconda3\python.exe scripts\compare_dense_remote_parity.py --index-dir "data/chunk metadata"
```

The first deployment should not be accepted until fixed smoke queries have
matching top-1/top-5/top-10 IDs and citation metadata.

## Docker Build

From repository root:

```bash
docker build -f deployment/retrieval_runpod/Dockerfile -t lexvn-retrieval-runpod .
```

## Docker Run With Local Artifacts

```bash
docker run --rm --gpus all \
  -p 8000:8000 -p 8001:8001 \
  -e DENSE_API_KEY=local-secret \
  -e BM25_API_KEY=local-secret \
  -e DENSE_EXPECTED_MODEL=intfloat/multilingual-e5-large \
  -e DENSE_EXPECTED_INDEX_VERSION=chunk-metadata-faiss-v1 \
  -e DENSE_DEVICE=cuda \
  -e BM25_INDEX_DIR=/workspace/bm25_service/bm25/shards \
  -e BM25_PAYLOAD_CACHE_PATH=/workspace/artifacts/dense/payload_cache.sqlite \
  -e BM25_SEARCH_WORKERS=4 \
  -v "$PWD/artifacts:/workspace/artifacts" \
  -v "/path/to/existing/bm25_service:/workspace/bm25_service:ro" \
  lexvn-retrieval-runpod
```

For CPU-only local Docker smoke tests, omit `--gpus all` and set
`DENSE_DEVICE=cpu`.

If you want to smoke test against the old local single-index BM25 layout
instead, replace the BM25 env and mount with:

```bash
-e BM25_INDEX_DIR=/workspace/local_bm25 \
-v "$PWD/data/sparse_index:/workspace/local_bm25:ro"
```

## RunPod Steps

1. Build the Docker image.
2. Push it to your container registry.
3. Create or select persistent storage.
4. Upload Dense artifacts into `/workspace/artifacts/dense`.
5. Confirm existing BM25 shards are mounted at `/workspace/bm25_service/bm25/shards`.
6. Upload or warm Hugging Face cache under `/workspace/artifacts/cache`.
7. Create a GPU Pod from the image.
8. Mount persistent storage so both `/workspace/artifacts` and `/workspace/bm25_service` are available. If your Network Volume is already mounted at `/workspace`, keep that layout.
9. Configure environment variables and secrets.
10. Expose ports `8000` and `8001`.
11. Launch the container.
12. Test Dense `/healthz`, `/readyz`, `/version`, and `/search`.
13. Test BM25 `/healthz` and `/bm25`.
14. Set UI env vars `DENSE_SERVICE_URL` and `BM25_SERVICE_URL`.
15. Run an end-to-end UI smoke question and confirm diagnostics show `filter_profile=current_law`, Dense-Sparse retrieval, and BM25 resident indexes/search workers.

Do not hard-code Pod IDs, proxy URLs, or secrets into the repository.
