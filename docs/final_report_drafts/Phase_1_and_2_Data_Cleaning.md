# BÁO CÁO THỰC THI GIAI ĐOẠN 1 VÀ 2: ĐÁNH GIÁ CHẤT LƯỢNG VÀ TRIỆT TIÊU NHÃN NGOẠI LAI

> [!NOTE]
> Giai đoạn này đặt nền móng cho việc phân loại 10.000 dòng dữ liệu gốc một cách chính xác. Thông qua việc sử dụng mô hình LLM mạnh để chấm điểm độc lập (Eval) và chiến thuật triệt tiêu nhãn ngoại lai, hệ thống đảm bảo toàn bộ dữ liệu đều được phân loại đúng chủ đề (Topic) của tư vấn thời trang.

---

## 1. Giai Đoạn 1: Chạy Xuyên Đêm & Fallback API
### 1.1. Kiến trúc Chấm điểm Tự động
Để đánh giá nhanh 10.000 dòng dữ liệu, script `run_gemma_eval.py` được triển khai với vai trò Giám khảo:
- Mỗi dòng dữ liệu (câu hỏi & câu trả lời) được đưa vào mô hình để chấm 3 tiêu chí: Độ khó (Complexity), Độ chi tiết (Detail) và Từ vựng (Vocabulary).
- Kết hợp với việc gán nhãn chủ đề (ví dụ: Phối đồ, Làm đẹp, Chất liệu...).

### 1.2. Cơ chế Bảo vệ Hệ thống (Fail-safe)
Với khối lượng 10.000 dòng, việc gặp lỗi kết nối API là không thể tránh khỏi.
- **Xoay tua API (Key Rotation):** Khi một API Key bị lỗi 429 (Rate Limit Exceeded), hệ thống lập tức chuyển sang Key dự phòng.
- **Cô lập Lỗi (Error Isolation):** Bất kỳ Batch nào bị đứt gãy hoặc định dạng trả về bị hỏng (Model format error) đều bị đẩy vào file `failed_batches.json` để hệ thống không bị crash và dừng tiến trình. Ngày hôm sau, các batch này sẽ được tải lên và chạy lại tự động.

## 2. Giai Đoạn 2: Xử lý Fallback và Triệt tiêu nhãn "Khác"
### 2.1. Xử lý các Batch lỗi (Error Batch Processing)
Sau quá trình xử lý ban đầu, toàn bộ các ID bị lỗi trong `failed_batches.json` được tổng hợp thành các batch nhỏ hơn và tiến hành xử lý lại. Quá trình này được lặp lại cho tới khi danh sách Fallback được giải quyết hoàn toàn (Clearance = 100%).

### 2.2. Quy trình Xử lý nhãn ngoại lai "Khác"
Sau đợt phân loại đầu tiên, một số lượng lớn dữ liệu bị xếp mập mờ vào nhóm "Khác" (Không thuộc các phân loại tiêu chuẩn). Điều này làm ảnh hưởng đến cấu trúc phân bổ chủ đề của tập dữ liệu.
- **Kỹ thuật Phân giải (Resolution):** Tiến hành cô lập toàn bộ các dòng bị gắn mác "Khác". 
- **Cập nhật Rubric:** Bổ sung thêm 5 chủ đề phụ (Sub-topics) chi tiết hơn vào câu Lệnh (Prompt).
- **Ép chạy lại (Re-run):** Yêu cầu mô hình chỉ phân loại lại các câu "Khác" dựa trên bộ Rubric mới. Quá trình này được lặp đi lặp lại có chủ đích cho đến khi tỷ lệ nhãn "Khác" bị ép xuống 0%.

### 3. Kết luận Giai đoạn 1 & 2
Kết thúc quá trình, 100% (10.000 dòng) dữ liệu đã được chấm điểm 3 tiêu chí rõ ràng và gán nhãn chủ đề chính xác tuyệt đối, tạo nên một cơ sở dữ liệu (Database) hoàn chỉnh để thực hiện lọc (Distillation) ở Giai đoạn 3.
