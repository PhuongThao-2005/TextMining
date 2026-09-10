# Giao diện LexVN

Chạy từ thư mục gốc của dự án, trong môi trường Python đã cài `requirements.txt`:

```powershell
python -m streamlit run ui/app.py
```

Nhập câu hỏi ngay ở màn hình đầu. Chọn **Phạm vi** bên cạnh ô nhập: **Hiện hành**, **Mở rộng** hoặc **Lịch sử**. Sau khi có câu trả lời, ô hỏi tiếp nằm ở cuối màn hình. Nhấn trích dẫn `[1]`, **Xem bằng chứng** hoặc một nguồn để mở cùng một bảng bằng chứng; trên màn hình nhỏ, bảng mở rộng theo chiều ngang.

**Chế độ demo vẫn được giữ trong thanh bên để kiểm thử.** Câu trả lời demo dùng dữ liệu mẫu và không gọi mô hình hoặc dịch vụ truy xuất để trả lời. Production dùng cấu hình, truy xuất và mô hình hiện có; nếu dịch vụ chưa sẵn sàng, giao diện báo lỗi và không tự chuyển câu trả lời sang demo.

Nút biểu tượng trên đầu trang đổi giao diện sáng/tối. **Cài đặt** cho phép chọn tiếng Việt/English và giao diện hệ thống. Hội thoại chỉ thuộc phiên Streamlit hiện tại; **Câu hỏi mới** bắt đầu lại. Hỏi tiếp giữ các lượt trước để đọc lại, không bổ sung bộ nhớ hội thoại vào yêu cầu gửi backend.

## Công cụ dành cho nhà phát triển

Mặc định các điều khiển truy xuất, mô hình, prompt và chẩn đoán kỹ thuật được ẩn. Bật chúng bằng biến môi trường hoặc thêm vào `.env`:

```dotenv
SHOW_DEVELOPER_UI=true
```

Khởi động lại Streamlit sau khi đổi biến môi trường. Mục dành cho nhà phát triển giữ các điều khiển Dense/Dense-Sparse, Graph, Reranker, model, Base/CoT, xóa cache và thông tin readiness. Đặt `SHOW_DEVELOPER_UI=false` để trở về giao diện thông thường. Demo vẫn có thể chọn khi mục này bị ẩn.

## Kiểm tra giao diện

```powershell
python -m pytest tests/ui -q
```

Các kiểm tra luồng UI dùng Streamlit AppTest với readiness và provider giả lập, không cần chạy mô hình hoặc dịch vụ từ xa. Kiểm tra bố cục, độ tương phản và responsive cần mở ứng dụng trên trình duyệt.
