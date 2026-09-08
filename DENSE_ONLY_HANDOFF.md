# LexVN — Handoff chạy Dense Only

## 1. Trạng thái hiện tại

| Thành phần | Trạng thái |
| --- | --- |
| Dense | Ready |
| Dense Remote API | Ready |
| FAISS | Ready |
| multilingual-e5-large | Ready |
| Graph | Có thể phát triển/test với Dense candidates |
| Reranker | Có thể phát triển/test với Dense candidates |
| BM25 | Chưa sẵn sàng |
| Hybrid Dense-Sparse | Chưa dùng |

Hiện tại team chỉ chạy Dense Only để Graph và Reranker có nguồn candidates thực tế để phát triển và integration test.

Config production remote dense trong repo hiện là `Agent-None-RemoteDense`. Streamlit entrypoint hiện là `ui/app.py`.

Lưu ý theo code hiện tại: bật Graph trực tiếp với `dense_remote` trong UI cần thêm remote graph/payload hydration adapter. Reranker có thể test trên Dense candidates nếu môi trường local có package cần thiết.

## 2. Kiến trúc tạm thời

```text
Local Streamlit / Orchestrator
          |
          v
Dense Remote Client
          |
          v
RunPod Dense API :8000
          |
          v
multilingual-e5-large
          |
          v
FAISS + payload
          |
          v
Dense candidates
          |
          +----> Graph
          |
          +----> Reranker
          |
          v
LLM / UI
```

BM25 chưa nằm trong luồng này. Không bật Dense-Sparse/Hybrid/BM25 trong giai đoạn handoff Dense Only.

## 3. Chuẩn bị repo

```powershell
git pull
cd <repo-root>
```

Nếu chưa có môi trường Python:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu máy đang dùng Conda hoặc Python khác, dùng đúng interpreter đó:

```powershell
python -m pip install -r requirements.txt
```

Không cần tải FAISS index local để chạy Dense Only, vì FAISS và payload đã chạy remote trên RunPod.

## 4. Set environment variables

Set các biến này trong cùng terminal dùng để chạy Streamlit:

```powershell
$env:DENSE_SERVICE_URL="https://c439rymeynzki0-8000.proxy.runpod.net"
$env:DENSE_API_KEY="<DENSE_API_KEY>"
$env:DENSE_TIMEOUT_SECONDS="30"
$env:DENSE_EXPECTED_MODEL="intfloat/multilingual-e5-large"
$env:DENSE_EXPECTED_INDEX_VERSION="chunk-metadata-faiss-v1"
```

`DENSE_API_KEY` là secret. Không ghi key thật vào Markdown, không commit vào Git. Lấy key riêng từ thành viên phụ trách deployment.

Nếu hỏi qua UI production và cần sinh câu trả lời, app cũng cần LLM env:

```powershell
$env:LLM_BASE_URL="<OPENAI_COMPATIBLE_BASE_URL>"
$env:LLM_API_KEY="<LLM_API_KEY>"
$env:LLM_BASE_MODEL="gpt-4o-mini"
```

Không set BM25 env trong hướng dẫn Dense Only.

## 5. Kiểm tra Dense production trước khi chạy app

```powershell
Invoke-RestMethod `
  -Uri "$env:DENSE_SERVICE_URL/readyz" `
  -Headers @{ Authorization = "Bearer $env:DENSE_API_KEY" }
```

Expected:

```text
status = ready
embedding_model = intfloat/multilingual-e5-large
embedding_dimension = 1024
index_version = chunk-metadata-faiss-v1
vector_count = 1513376
payload_count = 1513376
```

## 6. Test Dense search trực tiếp

```powershell
$body = @{
    query = "Người lao động được nghỉ phép năm bao nhiêu ngày?"
    top_k = 20
    top_n = 5
    filter_profile = "current_law"
} | ConvertTo-Json -Depth 10

$utf8Body = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
    -Method Post `
    -Uri "$env:DENSE_SERVICE_URL/search" `
    -Headers @{
        Authorization = "Bearer $env:DENSE_API_KEY"
    } `
    -ContentType "application/json; charset=utf-8" `
    -Body $utf8Body

$response.hits |
    Select-Object rank,title,article_number,validity_group,vector_score

$response.latency_ms
```

Nếu có `hits` thì remote Dense hoạt động. `current_law` nên dùng cho query pháp luật hiện hành. `broad` có thể trả văn bản expired nên không dùng làm mặc định cho demo pháp luật hiện hành.

## 7. Chạy Streamlit

```powershell
streamlit run ui/app.py
```

Hoặc dùng script repo:

```powershell
.\scripts\start_ui_local.ps1
```

Mở:

```text
http://localhost:8501
```

Trong UI:

- Chọn `Production`.
- Chọn `Dense Only`.
- Không chọn `Dense-Sparse`/`Hybrid`.
- Graph/Reranker chỉ bật khi thành viên đang test phần tương ứng.
- BM25 chưa dùng.

Nếu đã đổi env hoặc config khi app đang mở, bấm `Clear resource cache` trong sidebar rồi hỏi lại.

## 8. Query test đề xuất

- Người lao động được nghỉ phép năm bao nhiêu ngày?
- Điều kiện thành lập doanh nghiệp là gì?
- Quy định về hợp đồng lao động là gì?
- Điều kiện cấp giấy phép xây dựng là gì?
- Doanh nghiệp có nghĩa vụ nộp thuế như thế nào?

## 9. Cách xác nhận app thật sự gọi RunPod Dense

Khi hỏi từ UI, Dense RunPod logs phải xuất hiện:

```text
POST /search HTTP/1.1 200 OK
```

Local app không nên load FAISS index local. Dense candidates phải đến từ `DENSE_SERVICE_URL`.

Có thể kiểm tra nhanh trong repo:

```powershell
Get-ChildItem -Recurse -Include *.py,*.yaml,*.yml,*.toml |
  Select-String -Pattern "localhost:8000|127.0.0.1:8000|DENSE_SERVICE_URL|dense_remote"
```

## 10. Graph và Reranker integration

Graph và Reranker có thể được phát triển độc lập trước. Input nên lấy từ Dense candidates.

Schema chung hiện tại nằm ở `src/retrieval/schema.py`, dataclass `RetrievedChunk`. Các field chính:

- `chunk_id`
- `chunk_text`
- `citation_anchor`
- `citation_label`
- `title`
- `article_number`
- `unit_type`
- `path`
- `validity_group`
- `legal_authority_rank`
- `vector_score`
- `rerank_score`
- `id_str`
- `parent_unit_id`
- `metadata`

Flow integration:

```text
Query
 -> Dense
 -> Dense candidates
 -> optional Graph
 -> optional Reranker
 -> downstream answer
```

Không cần BM25 để phát triển/test Graph hoặc Reranker ở giai đoạn này.

Ghi chú code hiện tại: Graph với `dense_remote` trong UI còn cần remote graph/payload hydration adapter. Nếu chỉ test thuật toán Graph độc lập, lấy `RetrievedChunk` từ Dense làm input fixture hoặc adapter trung gian.

## 11. BM25 — trạng thái hiện tại

BM25 hiện chưa được bật trong workflow handoff này.

Lý do:

- BM25 sharded hiện có vấn đề memory khi load/search.
- Đã quan sát memory tăng rất cao và có OOM.
- Sẽ xử lý BM25/deployment riêng sau.
- Không để BM25 làm blocker cho Graph/Reranker.

Không hướng dẫn workaround giả hoặc chạy BM25 local trong handoff Dense Only.

## 12. Troubleshooting

### 401 Unauthorized

`DENSE_API_KEY` sai hoặc chưa set. Set lại key trong cùng PowerShell đang dùng để chạy Streamlit.

### 403 Cloudflare / browser signature

Repo hiện đã thêm browser-like `User-Agent` trong remote Dense client. Nếu gặp lại lỗi này, kiểm tra code đang chạy có phải bản mới nhất không.

### 502 / connection error

Kiểm tra Dense RunPod Pod còn `Running` và `/readyz` có trả `ready`.

```powershell
Invoke-RestMethod `
  -Uri "$env:DENSE_SERVICE_URL/readyz" `
  -Headers @{ Authorization = "Bearer $env:DENSE_API_KEY" }
```

### App báo socket error trên Windows

- Dừng Streamlit bằng `Ctrl+C`.
- Set lại env trong cùng PowerShell.
- Test `/readyz`.
- Chạy lại Streamlit.
- Kiểm tra app không gọi `localhost:8000` hoặc `127.0.0.1:8000`.

```powershell
Get-ChildItem -Recurse -Include *.py,*.yaml,*.yml,*.toml |
  Select-String -Pattern "localhost:8000|127.0.0.1:8000|DENSE_SERVICE_URL|dense_remote"
```

### Tiếng Việt hiển thị dạng Äiá»...

Dataset/payload trên RunPod đã được kiểm tra UTF-8 đúng. Nếu PowerShell hiển thị mojibake thì đó có thể là terminal encoding.

```powershell
chcp 65001
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
```

Không rebuild Dense index chỉ vì terminal hiển thị lỗi encoding.

## 13. Checklist trước khi handoff test Graph/Reranker

- [ ] Dense RunPod Pod đang Running
- [ ] `/readyz` trả `ready`
- [ ] `DENSE_SERVICE_URL` đã set
- [ ] `DENSE_API_KEY` đã set
- [ ] `/search` trả hits
- [ ] Streamlit chạy bằng `ui/app.py`
- [ ] UI đang ở Dense Only
- [ ] Không bật BM25/Hybrid
- [ ] Graph có thể nhận Dense candidates
- [ ] Reranker có thể nhận Dense candidates

## 14. Trạng thái cuối

```text
Dense deployment: READY
Dense-only integration: READY FOR TEAM TESTING
Graph: READY TO INTEGRATE AGAINST DENSE
Reranker: READY TO INTEGRATE AGAINST DENSE
BM25: PENDING
```
