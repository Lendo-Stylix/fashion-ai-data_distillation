# TỔNG QUAN HỆ THỐNG: CHUỖI 5 GIAI ĐOẠN CHUẨN BỊ VÀ CHƯNG CẤT DỮ LIỆU (FASHION AI)

> [!NOTE]
> Tài liệu này mô tả Master Plan tổng thể của toàn bộ hệ thống chuẩn bị dữ liệu. Quá trình này đã trải qua nhiều lần tinh chỉnh và thay đổi so với dự kiến ban đầu nhằm ứng phó với các giới hạn về API Rate Limit và hiện tượng ảo giác (hallucination) của các mô hình ngôn ngữ lớn. Kết quả cuối cùng là một tập dữ liệu 1.488 mẫu chất lượng hoàn hảo có khả năng sinh lập luận sâu (reasoning).

---

## Giai đoạn 1: Chấm điểm Tự động & Xử lý Fallback (Đã Hoàn Thành)
- Script `run_gemma_eval.py` được triển khai để tự động chấm điểm 10.000 dòng dữ liệu gốc dựa trên Rubric đánh giá (Complexity, Detail, Vocabulary).
- **Cơ chế:** Kích hoạt tính năng xoay vòng API Key tự động khi gặp lỗi 429 (Rate Limit). Mọi batch lỗi (model format sai, thiếu ID) được cô lập vào `failed_batches.json` và được xử lý lại bằng cron job vào buổi sáng.

## Giai đoạn 2: Triệt tiêu Nhãn Ngoại Lai "Khác" (Đã Hoàn Thành)
- **Vấn đề:** Nhiều dữ liệu bị mô hình gán tag "Khác" (Không xác định được chủ đề).
- **Xử lý:** Bổ sung thêm 5 tag mới cụ thể vào Rubric và ép mô hình chạy lại CHỈ TRÊN các dòng "Khác" này. Quá trình lặp lại cho đến khi tỷ lệ nhãn "Khác" giảm xuống còn 0%, đảm bảo phân loại dữ liệu tuyệt đối chính xác.

## Giai đoạn 3: Phân tích Chất lượng & Áp dụng Lý thuyết LIMA/DEITA (Đã Hoàn Thành)
Dựa trên nền tảng khoa học chuẩn vàng về Data Distillation:
- **Bước 1 (Bộ lọc DEITA):** Sàng lọc 10.000 dòng thành tập "Ứng viên Tiềm năng" (4.015 dòng) với bộ tiêu chuẩn: Độ khó >= 2, Độ chi tiết == 3, Từ vựng >= 2.
- **Bước 2 (Lấy mẫu LIMA):** Áp dụng phương pháp Lấy mẫu Phân tầng (Stratified Sampling) để cân bằng tính đa dạng chủ đề. Tiến hành Over-sample các nhóm thiểu số và Under-sample nhóm phổ biến. Từ đó, tuyển chọn thành công **1.500 mẫu dữ liệu tiêu biểu**.

## Giai đoạn 4: Dịch thuật, Auto-Fix và Rà Soát (Đã Hoàn Thành)
Mục tiêu là dịch lại từ gốc Tiếng Anh đối với các dòng bị sượng hoặc sai nghĩa mà không xóa bỏ chúng.
- **Sự cố API & Giải pháp:** Kế hoạch ban đầu định dùng Gemma 26B, nhưng do cạn kiệt Quota liên tục, hệ thống đã tự động chuyển hướng sang kiến trúc **Model Fallback** xoay vòng các mô hình từ Alibaba (`qwen-plus`, `qwen-turbo`).
- **Auto-Fix Pipeline:** Hệ thống tích hợp "Lịch sử Lỗi" của vòng trước vào prompt, buộc mô hình tự động nhận diện và sửa chữa sai sót.
- **Bước Rà Soát Cuối (Harsh Sweeper):** Loại bỏ triệt để các đặc trưng văn bản của AI như cụm từ "Xin chào", "Nhìn chung", và các ký hiệu định dạng không phù hợp.
- **Kết quả:** Vượt qua quy trình kiểm định khắt khe, tuyển chọn được **1.488 mẫu dữ liệu đạt tiêu chuẩn tối ưu**.

## Giai đoạn 5: Kỹ Thuật Sinh Suy Luận (Reasoning Generation) (Đã Hoàn Thành)
Đây là giai đoạn phức tạp và mang tính thách thức cao nhất nhằm tạo lập thẻ `<think>` hướng dẫn tư duy cho AI.
- **Thử nghiệm 1 (Thất bại):** Sử dụng Qwen 3.7 Max và các bản nâng cấp. Mặc dù hệ thống Thread-safe hoạt động tốt, mô hình liên tục gặp lỗi loạn ngôn ngữ (Bilingual thinking) và ngốn sạch hơn 10 triệu token Quota một cách vô ích.
- **Thử nghiệm 2 - Pipeline Ver 3 (Thành công đột phá):** 
  - Đổi sang dùng mô hình `tencent/hy3:free` (Hunyuan 3) thông qua OpenRouter.
  - Thiết kế cơ chế **Reverse Prompting (3 Bước)**: (1) Sinh Câu trả lời -> (2) Đánh giá để chọn lựa câu trả lời cuối -> (3) Đưa ngược câu trả lời vào mô hình, yêu cầu mô phỏng lại toàn bộ quá trình phân tích (suy luận ngược) dẫn đến câu trả lời đó hoàn toàn bằng Tiếng Việt.
  - Điều chỉnh trần `max_tokens` lên mức 4000 để hệ thống có khả năng đáp ứng lượng token phát sinh từ tư duy ẩn (Internal Thinking) của mô hình.

**=> Kết quả Tổng thể:** Xuất xưởng tập dữ liệu cuối cùng `final_distilled_reasoning_1488_v3_chatml.jsonl` hoàn toàn sẵn sàng cho công tác Huấn luyện (Fine-Tuning) Qwen 3.5 tiếng Việt.
