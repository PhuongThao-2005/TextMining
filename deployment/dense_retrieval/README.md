# Dense retrieval trên RunPod

Service nhận câu hỏi, chạy E5 + FAISS và trả đầy đủ chunks/metadata cho UI.
Tái sử dụng `VectorRetriever`; không xây lại index. Embedding chạy GPU,
FAISS chạy CPU và payload được đọc từ SQLite. Dùng một worker cho một Pod.

## 1. Chạy thử local

Điền vào `.env` ở gốc repo:

```text
DENSE_INDEX_DIR=data/chunk metadata
DENSE_DEVICE=cpu
DENSE_SERVICE_URL=http://127.0.0.1:8002
DENSE_API_KEY=<khóa bí mật tự tạo>
HF_HOME=.cache/huggingface
```

Sau đó chạy trong PowerShell:

```powershell
.\run_dense.ps1
```

Service và script kiểm tra tự đọc `.env`; không cần đặt từng `$env:...`.
Nếu shell đã có cùng biến secret thì giá trị shell được ưu tiên.
Lần đầu cần tải model, đặt `HF_HUB_OFFLINE=0`; khi cache đã đủ có thể đặt `1`.
Nếu thiếu dependency, cài một lần bằng `.venv/Scripts/python.exe -m pip install -r requirements.txt`.
Trong terminal thứ hai, chạy:

```powershell
.venv/Scripts/python.exe scripts/check_dense_service.py --url http://127.0.0.1:8002
# Tùy chọn: nạp thêm một bản model/index để so sánh local với HTTP.
.venv/Scripts/python.exe scripts/check_dense_service.py --url http://127.0.0.1:8002 --compare-local
```

So sánh dùng 3 câu hỏi × 3 filter profiles, kiểm tra IDs, nội dung,
metadata trích dẫn và vector scores. Đây là smoke test, chưa phải benchmark.

## 2. Chuẩn bị Pod

Copy nguyên bộ artifact đã xác nhận từ `data/chunk metadata` tới volume:

```text
/workspace/dense-index/
  index.faiss
  payloads.jsonl
  payload_cache.sqlite
  index_manifest.json
  id_map.json             # giữ lại nếu bundle gốc có file này
```

Ba file dữ liệu chính hiện khoảng 18,2 GB. Cần thêm chỗ cho model cache.
Service dùng cache có sẵn, không sửa hoặc xây lại cache. Mtime thay đổi khi
copy được chấp nhận; schema và kích thước payload vẫn phải khớp. Copy cùng
một bundle, không ghép SQLite/FAISS từ các build khác nhau.

Manifest hiện tại được hỗ trợ trực tiếp. Startup đối chiếu model/corpus/index,
dimension, số vector và số payload, rồi chạy một truy vấn trước khi ready.
Không thực hiện checksum toàn bộ bundle mỗi lần khởi động.

Build image từ **gốc repo**, sau đó tag/push tới registry của bạn:

```sh
docker build -f deployment/dense_retrieval/Dockerfile -t dense-retrieval:v1 .
```

Image chỉ chứa code/dependencies; bộ artifact nằm trên volume.
Dockerfile.dockerignore loại dữ liệu, `.env` và cache khỏi build context.
Chọn Pod có đủ host RAM cho index ~6,2 GB cộng model/runtime; đo thực tế trước
khi chốt cấu hình GPU. Dependencies chưa có lockfile; lưu image digest sau build.

Đặt environment trên Pod:

```text
DENSE_INDEX_DIR=/workspace/dense-index
DENSE_DEVICE=cuda
DENSE_API_KEY=<khóa riêng>
HF_HOME=/workspace/huggingface
```

Giữ cache model trên volume. Lần đầu cần tải model nếu cache chưa có.
Container chạy Uvicorn tại `0.0.0.0:8002`; expose HTTP port `8002`.
URL có dạng `https://<pod-id>-8002.proxy.runpod.net`.
Proxy công khai và giới hạn kết nối 100 giây, vì vậy phải cấu hình API key.
Xem [RunPod ports](https://docs.runpod.io/pods/configuration/expose-ports)
và [storage](https://docs.runpod.io/pods/storage/types).

## 3. Nối UI

Sau khi smoke test endpoint thành công, sửa `.env` trên máy UI:

```text
DENSE_BACKEND=dense_remote
DENSE_SERVICE_URL=https://<pod-id>-8002.proxy.runpod.net
DENSE_API_KEY=<cùng khóa trên Pod>
DENSE_TIMEOUT_SECONDS=30
```

Khởi động lại UI. Chọn **Dense Only**, tắt Graph và Reranker.
UI dùng config `Dense-Remote-E2E`, kiểm tra `/version` và `/readyz`, rồi gọi
`/search`. Diagnostics ghi model/corpus/index, request ID và latency.
Đổi `DENSE_BACKEND=faiss` và restart để quay lại local.

Dense remote v1 chưa hỗ trợ hybrid/graph/cross-encoder. Các cấu hình local
hiện có tiếp tục hoạt động. Không có fallback tự động khi remote lỗi.

## API và lỗi

- `GET /healthz`: liveness sau khi startup hoàn tất.
- `GET /readyz`: thành công khi model/index/cache tương thích.
- `GET /version`: service/model/corpus/index identity.
- `POST /search`: query, top_k (1–150), top_n (1–50, không quá top_k),
  filter_profile (`broad`, `current_law`, `historical`), score_threshold,
  expand_units và request_id tùy chọn.
- Tất cả endpoint kiểm tra Bearer token khi `DENSE_API_KEY` được đặt.
- 401: sai khóa; 422: request không hợp lệ; 429: service đang bận;
  503: chưa ready; 500: retrieval thất bại. Kết quả rỗng trả 200, `hits=[]`.
- Mỗi Pod xử lý một search tại một thời điểm; request đồng thời nhận 429.
  Client retry tối đa 2 lần với lỗi mạng hoặc 429/502/503/504, không retry 4xx khác.

## Kiểm thử

```powershell
.venv/Scripts/python.exe -m pytest tests/retrieval/test_dense_remote.py tests/ui/test_dense_remote_config.py -q
```

Test offline dùng FAISS/SQLite thật với dữ liệu nhỏ và hashing embedder.
Chúng kiểm tra HTTP parity, citation, filter/expansion, auth, validation,
timeout/retry, request đồng thời và cache chỉ đọc. Trước rollout production,
cần chạy so sánh với E5/artifact thật, đo warm p50/p95 và RAM/VRAM trên Pod.

Kiểm tra tại máy phát triển: suite liên quan đã qua; bộ FAISS/SQLite thật
đã nạp và qua kiểm tra dimension/cardinality. Smoke với model E5 thật chưa
hoàn tất vì cache local thiếu file model. Máy hiện dùng PyTorch CPU;
Docker image và GPU RunPod chưa được kiểm chứng ở đây.
