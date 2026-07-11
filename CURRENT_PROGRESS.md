# Báo Cáo Tiến Độ Dự Án (Project State & Next Steps)

**Dự án:** Data Pipeline for Qwen 3.5 Fine-Tuning (Fashion AI)
**Cập nhật lần cuối:** Sau khi hoàn thành Pilot Run (Phần 2 - Giai đoạn 5). Script chạy được 2/3 dòng thành công khi bàn giao.

---

## 1. Trạng Thái Hiện Tại (Current Status)
- **Tiến độ Pipeline:** Đang ở **Giai đoạn 5 (Sinh Reasoning & Cross-Check)** — Pilot Run đã chạy thành công.
- **Hoàn thành mới nhất (Pilot Run):**
  - Đã viết và debug hoàn chỉnh script `src/reasoning_generation/pilot_run.py`.
  - API `qwen3.7-plus` (DashScope international) kết nối thành công.
  - 2/3 dòng pilot cho kết quả `CLOUD_SUPERIOR` — hệ thống Cross-check hoạt động đúng.
  - **Vấn đề phát hiện:** Thinking_Cloud đang suy luận bằng tiếng Anh (cần cân nhắc có nên ép tiếng Việt không).
- **Output mới nhất:** `data/reasoning_generation/pilot_run_log.json` (JSON log đầy đủ thinking + answers)

## 2. Thư mục Làm việc Chính (Active Workspaces)
- **Code chính:** `src/reasoning_generation/pilot_run.py`
- **Data:** `data/reasoning_generation/` (`stratified_1488.csv` + `pilot_run_log.json`)
- **Tài liệu:** `docs/reports/phase5_and_finetune_strategy_report.md`

## 3. Cấu Hình Kỹ Thuật Quan Trọng (Đừng Quên!)
- **Model:** `qwen3.7-plus`
- **API Endpoint (HARD-CODED trong script):** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
  - ⚠️ KHÔNG dùng `DASHSCOPE_BASE_URL` trong `.env` — đó là MaaS endpoint riêng, không support model này.
- **API Key:** `DASHSCOPE_API_KEY_1` (từ `.env`)
- **Timeout:** 240s (model nặng, mỗi dòng mất 3-4 phút)
- **Cách chạy:** `$env:PYTHONUTF8=1; python src/reasoning_generation/pilot_run.py`
- **Reasoning nằm trong field:** `message["reasoning_content"]` (KHÔNG phải inline `<think>` tags)

## 4. Nhiệm Vụ Tiếp Theo (Next Action)
**Tác vụ:** Đánh giá kết quả Pilot Run và quyết định bước tiếp theo.

1. Đọc file `data/reasoning_generation/pilot_run_log.json` để xem đầy đủ Thinking + A_Cloud cho cả 3 dòng.
2. Quyết định: **Thinking có cần ép tiếng Việt không?** (Hiện tại đang tiếng Anh)
3. Nếu OK → chạy full pipeline cho **1488 dòng** bằng cách đổi `N_SAMPLE = 1488` hoặc viết script batch với checkpoint.
4. Sau đó: Build JSONL chuẩn ChatML → chuẩn bị cho DoRA fine-tuning.

---
*(Ghi chú cho Agent: Hãy đọc kỹ file này khi bắt đầu một phiên hội thoại mới. Đọc thêm `data/reasoning_generation/pilot_run_log.json` để thấy ví dụ thực tế của Thinking_Cloud và A_Cloud.)*


---

## 1. Trạng Thái Hiện Tại (Current Status)
- **Tiến độ Pipeline:** Đã hoàn thành xuất sắc Giai đoạn 4 (Distillation) với 1488 dòng sạch. Đang ở **Giai đoạn 5 (Sinh Reasoning & Cross-Check)**.
- **Hoàn thành mới nhất (Stratified Batching):**
  - Đã phân bổ dữ liệu thành công bằng thuật toán **Priority-based Fixed-Size Batching** (`batch_size = 16`).
  - Dữ liệu hoàn hảo về mặt vật lý, sẵn sàng cho nạp batch mà không lo hiện tượng *Gradient Oscillation* hay bias cuối mảng.
- **Dữ liệu đầu ra mới nhất:** `data/reasoning_generation/stratified_1488.csv` (Mỗi dòng đã được gắn cột `batch_id`).

## 2. Thư mục Làm việc Chính (Active Workspaces)
Khi Agent bắt đầu session mới, hãy chú ý đến các khu vực này:
- **Code:** `src/reasoning_generation/`
- **Data:** `data/reasoning_generation/` (Chứa file CSV đã chia batch)
- **Tài liệu/Báo cáo:** `docs/reports/phase5_and_finetune_strategy_report.md` và `docs/reports/phase5_part1_stratified_batching_report.md`

## 3. Nhiệm Vụ Tiếp Theo (Next Action)
**Tác vụ:** Viết script Pilot Run cho quá trình Cross-Check (Chạy thử 5 dòng đầu tiên).
**Mục tiêu:**
1. Trích xuất 5 dòng đầu tiên từ file `stratified_1488.csv`.
2. Dùng Cloud API (DeepSeek / Qwen / Gemini - *chờ User chỉ định*) để truyền câu hỏi vào Prompt Sinh Reasoning + Trả lời.
3. Chạy qua hệ thống Prompt Giám Khảo (Cross-check 4-Category: `VERIFIED_EQUAL`, `DATASET_SUPERIOR`, `CLOUD_SUPERIOR`, `REJECTED`) để đánh giá chéo giữa câu trả lời gốc (`A_Dataset`) và câu trả lời của Cloud (`A_Cloud`).
4. Xuất log ra màn hình hoặc file nháp để User đánh giá chất lượng prompt.

---
*(Ghi chú cho Agent: Hãy đọc kỹ file này khi bắt đầu một phiên hội thoại mới để tiếp tục mạch công việc ngay lập tức mà không cần hỏi lại lịch sử.)*
