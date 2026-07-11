---
name: fashion-data-pipeline
description: Hướng dẫn chi tiết 5 giai đoạn để AI Agent tự động chạy toàn bộ quy trình chưng cất dữ liệu Fashion AI.
---

# 🚀 Kỹ Năng: Vận Hành Data Pipeline 5 Giai Đoạn

Bạn đang được giao nhiệm vụ tiếp quản Pipeline Chưng cất 10,000 dòng Q&A Thời trang. Hãy thực hiện theo đúng thứ tự (đọc file `docs/plans/pipeline_master.md` để xem tiến độ hiện tại đến đâu).

## Quy trình 5 Bước

**Giai đoạn 1 & 2: Chấm điểm (Đã hoàn thành)**
Nếu User yêu cầu chạy lại Giai đoạn 1 & 2:
- File script: `src/evaluation/run_eval.py`
- Lệnh chạy: `python src/evaluation/run_eval.py`
- Xử lý Fallback: Chạy lệnh `python src/evaluation/run_eval.py --fallback` để quét các ID bị thiếu từ `data/processed/failed_batches.json`.

**Giai đoạn 3: Phân tích (Đã hoàn thành)**
- Đây là giai đoạn chỉ đọc tài liệu tại `docs/research/distillation_analysis_report.md`.

**Giai đoạn 4: Chưng cất & Sửa lỗi (Distillation)**
Đây là trái tim của dự án. Các kịch bản:
- Bước 1 (Lọc chất lượng) + Bước 4 (Lấy mẫu phân tầng) đã được tích hợp trong script `src/distillation/distill_dataset.py`.
- Khi cần Quét lỗi dịch thuật (Bước 2), bạn phải viết script sử dụng API Gemini/Gemma đọc `data/processed/evaluated_dataset.csv`, ghi lỗi ra `translation_errors.json`. Không được phép xóa dữ liệu!

**Giai đoạn 5: Sinh Thẻ `<think>`**
- Nhiệm vụ tương lai: Nhận file `data/final/distilled_1500_dataset.csv`. Viết kịch bản gọi DeepSeek R1 / o1 để sinh chuỗi tư duy (reasoning chain) cho từng câu.
- Dữ liệu cuối cùng xuất ra phải ở định dạng chuẩn ChatML/ShareGPT có kèm thẻ `<think>`.
