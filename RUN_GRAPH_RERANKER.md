# Chạy LexVN

Backend tự khởi động Dense, BM25, Graph và Reranker trên RunPod; giao diện chạy
trên máy cá nhân. Không cần mở SSH, tunnel hoặc Web Terminal.

## Mỗi lần sử dụng

### 1. Bật Pod

Vào RunPod, mở Pod `dense-migration` và bấm **Start**.

Đợi khoảng 1–2 phút để bốn HTTP service hiện `Ready`:

```text
Dense      :8000
BM25       :8001
Graph      :8002
Reranker   :8003
```

### 2. Bật giao diện

Trong PowerShell tại thư mục dự án:

```powershell
.\scripts\start_ui_local.ps1
```

Mở <http://localhost:8501>.

### 3. Chọn chế độ

```text
Production
Dense-Sparse
Graph: ON
Reranker: ON
```

Sau đó nhập câu hỏi và bấm **Hỏi**.

## Khi dùng xong

Nhấn `Ctrl+C` tại terminal chạy UI và bấm **Stop** trên RunPod để tránh phát sinh
phí GPU. Không cần lưu thủ công: index, Graph, model cache và gói startup đều ở
network volume `/workspace`.

## Nếu app báo bị chặn

- Đợi thêm 1–2 phút vì Graph đang nạp.
- Restart UI nếu vừa restart hoặc đổi Pod.
- Kiểm tra bốn HTTP service trên RunPod đều hiển thị `Ready`.
- Nếu RunPod tạo Pod ID mới, cập nhật bốn `*_SERVICE_URL` trong `.env`, rồi restart UI.
