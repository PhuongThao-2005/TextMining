# Run LexVN Remote Dense + Hybrid

Handoff ngắn: production retrieval hiện đã chạy được remote trên RunPod.

```text
RunPod
├── Dense service :8000
└── BM25 service  :8001
```

UI local chỉ gọi HTTP tới RunPod, không cần chạy Dense/BM25 local và không cần local FAISS artifacts.

## Đã chạy được

```text
Production → Dense Only
Production → Dense-Sparse / Hybrid
```

Hybrid flow:

```text
Question
├── Remote Dense
└── Remote BM25
      ↓
  chạy song song
      ↓
  Weighted RRF
      ↓
  Generation + citations
```

Default production:

```text
Retrieval mode = Dense-Sparse
Filter profile = current_law
Dense weight   = 1.0
BM25 weight    = 0.3
RRF k          = 60
```

## Cài dependencies

```powershell
python -m pip install -r requirements.txt
```

## `.env` tối thiểu

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=<YOUR_LLM_API_KEY>
LLM_BASE_MODEL=gpt-4.1-mini

DENSE_SERVICE_URL=https://<RUNPOD_ID>-8000.proxy.runpod.net
DENSE_API_KEY=<DENSE_API_KEY>
DENSE_EXPECTED_MODEL=intfloat/multilingual-e5-large
DENSE_EXPECTED_INDEX_VERSION=chunk-metadata-faiss-v1

BM25_SERVICE_URL=https://<RUNPOD_ID>-8001.proxy.runpod.net
BM25_API_KEY=<BM25_API_KEY>
BM25_INDEX_VERSION=lexvn-bm25-v1
```


## Probe service trước

Dense:

```powershell
Invoke-RestMethod `
  -Uri "$env:DENSE_SERVICE_URL/readyz" `
  -Headers @{ Authorization = "Bearer $env:DENSE_API_KEY" }
```

Kỳ vọng:

```text
status = ready
```

BM25:

```powershell
Invoke-RestMethod `
  -Uri "$env:BM25_SERVICE_URL/healthz" `
  -Headers @{ Authorization = "Bearer $env:BM25_API_KEY" }
```

Kỳ vọng:

```text
status = ok
resident_index_count = 10
```

## Start UI

```powershell
python -m streamlit run ui/app.py
```

Mở:

```text
http://localhost:8501
```

## Test trong UI

Dense only:

```text
Mode: Production
Retrieval: Dense Only
Filter: Current
```

Hybrid remote:

```text
Mode: Production
Retrieval: Dense-Sparse
Filter: Current
```

Nếu mới đổi `.env` hoặc đổi Pod URL, bấm `Clear resource cache` trong UI.

## Lỗi thường gặp

```text
HTTP 401/403:
  kiểm tra DENSE_API_KEY / BM25_API_KEY

Sai Pod URL:
  DENSE_SERVICE_URL dùng port 8000
  BM25_SERVICE_URL dùng port 8001

BM25 chưa ready:
  đợi preload xong rồi gọi lại /healthz

Production preflight chưa sẵn sàng:
  kiểm tra Dense /readyz = ready và BM25 /healthz = ok
```

## Graph và Reranker remote

Image kế tiếp chạy thêm Graph ở port `8002` và Reranker ở port `8003`.

Graph artifact:

```text
/workspace/artifacts/graph/knowledge_graph.gpickle
```

Graph dùng lại `/workspace/artifacts/dense/payload_cache.sqlite`; không sao chép
FAISS. Cấu hình trên Pod:

```env
ENABLE_GRAPH=true
ENABLE_RERANKER=true
GRAPH_API_KEY=<SECRET>
RERANKER_API_KEY=<SECRET>
GRAPH_PICKLE_PATH=/workspace/artifacts/graph/knowledge_graph.gpickle
GRAPH_PAYLOAD_CACHE=/workspace/artifacts/dense/payload_cache.sqlite
RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
RERANKER_DEVICE=cuda
RERANKER_BATCH_SIZE=2
HF_HUB_OFFLINE=0
```

Cấu hình trên máy chạy UI:

```env
GRAPH_SERVICE_URL=https://<RUNPOD_ID>-8002.proxy.runpod.net
GRAPH_API_KEY=<SECRET>
RERANKER_SERVICE_URL=https://<RUNPOD_ID>-8003.proxy.runpod.net
RERANKER_API_KEY=<SECRET>
```

Sau khi đổi biến, restart Pod và bấm `Clear resource cache` trong UI. Thử lần
lượt Dense-Sparse, thêm Reranker, thêm Graph, rồi bật cả Graph + Reranker.
