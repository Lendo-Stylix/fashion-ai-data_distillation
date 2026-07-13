# Walkthrough — Báo cáo Kết quả Chuẩn bị Dataset Fine-tuning Qwen 3.5

Giai đoạn tiền xử lý và kiểm định dữ liệu cho bước huấn luyện Qwen 3.5 (4B) sử dụng Unsloth trên Kaggle (2xT4 GPU) đã hoàn thành xuất sắc. Dữ liệu đã 100% sạch, được sắp xếp đúng thứ tự batch stratified và chuyển đổi sang định dạng JSONL ChatML tiêu chuẩn.

---

## 1. Kết quả Tiền xử lý Dữ liệu (Preprocessing)
Chúng ta đã chạy thành công script [prepare_finetuning_dataset.py](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/src/final_phase_prepare_for_finetuning/prepare_finetuning_dataset.py) và tạo ra 2 tệp đầu ra quan trọng:
1. **CSV Gom nhóm:** [final_distilled_reasoning_1488_v3_grouped.csv](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/data/final/final_distilled_reasoning_1488_v3_grouped.csv)
   - Đã được sắp xếp tăng dần theo `batch_id` (từ 1 đến 93) và `ID` để gom 16 dòng thuộc cùng một batch vật lý nằm liền kề nhau.
2. **JSONL ChatML:** [final_distilled_reasoning_1488_v3_chatml.jsonl](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/data/final/final_distilled_reasoning_1488_v3_chatml.jsonl)
   - Định dạng ChatML chuẩn dành cho Unsloth.
   - Cột `system` content đã được thay đổi thành: `"Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt một cách chuyên nghiệp"`.
   - Phần suy luận `<think>...</think>` được đặt đúng vị trí ở đầu cột `assistant` content.

---

## 2. Kết quả Xác minh Dữ liệu (Verification)
Script xác thực [verify_finetuning_dataset.py](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/src/final_phase_prepare_for_finetuning/verify_finetuning_dataset.py) đã chạy qua 6 bước kiểm tra nghiêm ngặt và lưu lại file báo cáo chi tiết tại [verification_report.txt](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/data/final/verification_report.txt).

### Tóm tắt Trạng thái Kiểm định:
* **Assertion 1 (Đếm số dòng):** **PASSED** (Khớp chính xác 1488 dòng trên cả CSV và JSONL).
* **Assertion 2 (Tính liên tục của Batch):** **PASSED** (Không có batch_id nào bị phân mảnh, các batch_id chạy tuần tự).
* **Assertion 3 (Kích thước Batch cố định):** **PASSED** (Mỗi batch_id chứa đúng 16 dòng, tổng cộng 93 batches).
* **Assertion 4 (Xác thực tính Stratified):** **PASSED** (Độ lệch tuyệt đối trung bình so với batch lý tưởng cực kỳ nhỏ là **0.274 dòng/batch**, đảm bảo phân bổ tag thời trang cân bằng hoàn hảo trong từng batch để chống hiện tượng Gradient Oscillation).
* **Assertion 5 (Định dạng ChatML & `<think>`):** **PASSED** (Cấu trúc conversations 3 thành phần đúng luật; 100% dòng assistant bắt đầu bằng `<think>` và có thẻ đóng đầy đủ).
* **Assertion 6 (Mã hóa UTF-8):** **PASSED** (Được mã hóa UTF-8 không BOM, hiển thị tiếng Việt hoàn hảo).

### Thống kê Phân bổ Tag chính toàn cục:
* **Kiến thức cơ bản:** 45.77% (681 dòng)
* **Hoàn cảnh:** 28.63% (426 dòng)
* **Dáng người:** 16.80% (250 dòng)
* **Phong cách:** 5.85% (87 dòng)
* **Mua sắm & Quản lý tủ đồ:** 2.02% (30 dòng)
* **Phong thái & Tâm lý:** 0.47% (7 dòng)
* **Bảo quản & Thời trang bền vững:** 0.40% (6 dòng)
* **Làm đẹp & Chăm sóc cá nhân:** 0.07% (1 dòng)

---

## 3. Tối ưu hóa Tham số & Hướng dẫn Fine-tuning trên Kaggle
Dựa vào phân tích token thực tế của Qwen trên 1488 dòng:
* **Max token length:** 1196 tokens
* **95% Percentile (p95):** **859 tokens**

> [!TIP]
> **Khuyến nghị Seq Length:** Đặt `max_seq_length = 1024` trong cấu hình Unsloth là mốc tối ưu nhất (bao phủ ~98.5% tập dữ liệu, tiết kiệm tối đa VRAM và tăng tốc độ train trên 2xT4 GPU). Nếu muốn bao phủ 100% dòng dài nhất, hãy đặt `max_seq_length = 1280`.

### Các bước tiếp theo trên Kaggle:
1. Tải file dataset [final_distilled_reasoning_1488_v3_chatml.jsonl](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/data/final/final_distilled_reasoning_1488_v3_chatml.jsonl) lên Dataset của Kaggle.
2. Tạo Notebook Kaggle mới, cấu hình Accelerator là **GPU T4 x2**.
3. Copy-paste các cell code từ phần thiết kế notebook trong [implementation_plan.md](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/docs/final_phase_prepare_for_finetuning/implementation_plan.md).
4. Thay thế đường dẫn file dataset của bạn trong Cell 4 và thay đổi token Hugging Face / username của bạn trong Cell 2 & Cell 5.
5. Chạy thử nghiệm **Version 1** ($r=8, \alpha=16$) trước để kiểm định khả năng suy luận, sau đó chạy **Version 2** ($r=16, \alpha=32$) để so sánh.
