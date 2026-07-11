# TỔNG QUAN PIPELINE: Chiến dịch Lọc & Đánh giá Dữ liệu 10k bằng Gemma 4 31B

Chiến dịch này sẽ khởi chạy script `run_gemma_eval.py` với sự giám sát tự động để hoàn thành việc chấm điểm 10.000 dòng dữ liệu, sau đó thực hiện thống kê, chắt lọc (distill), sửa lỗi dịch, và cuối cùng là sinh dữ liệu suy luận (reasoning) phục vụ fine-tune Qwen 3.5.

## Lộ trình 5 Giai đoạn (5 Phases Pipeline)

**Giai đoạn 1: Chạy Xuyên Đêm & Fallback API (ĐÃ HOÀN THÀNH ✅)**
- Script `run_gemma_eval.py` đã được trang bị cơ chế tự động xoay vòng API Key khi gặp lỗi 429 (Rate Limit).
- Mọi batch bị hư hại (model format sai, thiếu ID) sẽ tự động được log vào `failed_batches.json` để không làm gián đoạn tiến trình.
- Tôi sẽ sử dụng công cụ `schedule` để tự động thức dậy kiểm tra file log vào sáng mai nhằm sửa lỗi hoặc chạy lại các batch thất bại.

**Giai đoạn 2: Xử lý Fallback & Triệt tiêu nhãn "Khác" (ĐÃ HOÀN THÀNH ✅)**
- *Nhật ký Hoạt động Xuyên Đêm:* Mọi hành động tôi làm khi thức dậy (check file nào, chạy bao nhiêu câu bị lỗi, tạo tag mới nào) đều sẽ được tôi cẩn thận ghi chép lại vào file `night_shift_log.md`.
- *Quét Fallback:* Sau khi hoàn thành 10.000 dòng, tôi sẽ rà soát `failed_batches.json`. Quá trình này sẽ gom các ID lỗi thành các batch 5 mới và chạy lại cho đến khi file fallback hoàn toàn trống rỗng.
- *Triệt tiêu nhãn "Khác":* Lọc ra toàn bộ các câu bị gán tag "Khác". Bổ sung 5 tag mới vào Rubric và ép model chạy lại CHỈ TRÊN các dòng "Khác" này. Quá trình lặp lại cho đến khi nhãn "Khác" đã bị triệt tiêu hoàn toàn xuống còn 0.

**Giai đoạn 3: Phân tích Chất lượng & Áp dụng Lý thuyết LIMA/DEITA (ĐÃ HOÀN THÀNH ✅)**
- Tiến hành thống kê sự phân bổ các tag sau khi đã triệt tiêu "Khác".
- Báo cáo phân tích chuyên sâu các phương pháp luận chuẩn vàng nhất về Data Distillation (LIMA và DEITA) để tìm ra công thức chưng cất dữ liệu phù hợp. 
- *Kết quả:* Toàn bộ lập luận khoa học đã được đúc kết vào file `distillation_analysis_report.md`.

---

**Giai đoạn 4: Thực thi Chưng cất (Distillation Pipeline) & Sửa Lỗi Dịch (ĐÃ HOÀN THÀNH ✅)**

Căn cứ vào kết quả phân tích ở Giai đoạn 3, chúng ta tiến hành chưng cất tập dữ liệu. **Đặc biệt lưu ý:** Sẽ *không xóa bỏ* bất kỳ dòng dữ liệu chất lượng cao nào dù chúng bị lỗi dịch thuật. Thay vào đó, ta sẽ truy tìm lỗi và *dịch lại từ bản gốc tiếng Anh* để bảo toàn tuyệt đối chất lượng của tập 10k.

- **Bước 1: Lọc theo Chất lượng & Phức tạp (DEITA Quality & Complexity)**
  Sử dụng điểm số do Gemma 4 chấm để thu hẹp từ 10,000 dòng xuống tập "Ứng viên Tiềm năng" (hiện tại đã xác định được **4,015 dòng**). (Tiêu chuẩn: Độ khó >= 2, Độ chi tiết == 3, Từ vựng >= 2).

- **Bước 2: Phân bổ Đa dạng Chủ đề (DEITA Diversity)**
  Từ 4,015 dòng, tiến hành lấy mẫu phân tầng (Stratified Sampling). Oversample các nhóm thiểu số (Làm đẹp, Mua sắm, Tâm lý...) và Undersample nhóm đa số để chốt sổ đúng **1,500 dòng** theo chuẩn LIMA.
  
- **Bước 3: Quét Lỗi Dịch Thuật Toàn Diện (Translation Audit)**
  Sử dụng mô hình Gemma 4 26B để quét toàn bộ 1.500 dòng.
  - **Cơ chế Batching:** Gom 10 dòng/request và ép cấu trúc trả về bằng Pydantic JSON Schema (`response_mime_type="application/json"`).
  - **Đầu ra:** Xuất ra file `translation_errors.json` chứa toàn bộ những ID bị lỗi (sai nghĩa, sượng, word-by-word) **kèm theo lý do lỗi chi tiết (Critique)** cho từng ID.

- **Bước 4: Dịch Lại & Tự Hiệu Đính Bằng Batch 3-Pass (Self-Refinement Pipeline)**
  Thực hiện vòng lặp "Dịch -> Chấm -> Sửa" với **Batch Size = 10 dòng** (Đã đo lường token: Max ~640, Mean ~192, P99 ~531 tokens. Với Batch 10, tổng Output token ~5000, hoàn toàn an toàn trong ngưỡng 8192 tokens của API).
  Luồng chạy sử dụng `google.genai` SDK + Pydantic JSON Schema + Try/Except `json.JSONDecodeError` để bắt lỗi và parse JSON tự động:
  - **Pass 1:** Đưa 10 dòng Raw gốc tiếng Anh + Lý do lỗi từ Bước 3 vào để model dịch lại sang tiếng Việt. Trả về JSON mảng 10 câu dịch.
  - **Pass 2:** Bơm 10 câu vừa dịch + Raw gốc để 26B làm Giám Khảo soi lỗi. Trả về JSON phân loại: `1. Hoàn hảo` hoặc `2. Lý do cần sửa`.
  - **Pass 3:** Lọc ra những ID không đạt `Hoàn hảo`, đưa bản dịch nháp + Raw gốc + Lý do cần sửa vào lại 31B để trau chuốt lần cuối. Trả về JSON bản dịch mượt mà nhất.
  - **Kết quả:** Sau các bước quét lỗi (Harsh Sweeper) và làm sạch tự động, tạo ra 1.488 dòng chất lượng hoàn hảo tuyệt đối (chuẩn 10/10).

---

**Giai đoạn 5: Sinh Suy Luận (Reasoning Generation) Dựa Trên Phân Tích Chuyên Sâu (ĐANG THỰC HIỆN 🔄)**

Giai đoạn này được tách riêng do tính chất phức tạp và tốn kém tài nguyên tính toán.
- **Mục tiêu:** Sinh thêm thẻ `<think>...</think>` (chứa luồng tư duy phân tích, lập luận logic của chuyên gia) bổ sung vào đầu mỗi câu trả lời của 1.488 dòng Final.
- **Phương pháp luận:** Sẽ có một bài research riêng để xác định mô hình (VD: DeepSeek R1, GPT-o1, Claude 3.5 Sonnet...) và phương pháp prompting tối ưu để tạo ra reasoning data chất lượng nhất cho trợ lý ảo thời trang.
- **Danh sách Models dự phòng cho Task Thinking (Đã được Sếp kiểm duyệt):** 
  `qwen3.5-plus-2026-02-15`, `qwen3.7-plus`, `qwen3.7-max-2026-06-08`, `qwen3.6-plus`, `qwen3.7-max-preview`, `qwen3.6-max-preview`, `qwen3.6-flash`, `qwen3.5-flash`, `qwen3.5-flash-2026-02-23`, `qwen3.7-max-2026-05-20`, `qwen3.7-plus-2026-05-26`, `qwen3.6-27b`, `qwen3.6-flash-2026-04-16`, `qwen3.5-27b`, `qwen3.7-max-2026-05-17`, `qwen3.5-plus`, `qwen3.7-max`, `qwen3.5-plus-2026-04-20`.
