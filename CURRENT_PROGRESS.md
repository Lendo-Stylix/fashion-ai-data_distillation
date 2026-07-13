# CURRENT_PROGRESS — Fashion AI Data Pipeline

**Cập nhật lần cuối:** 12/07/2026 16:00 UTC+7  
**Phase hiện tại:** Giai đoạn 6 — Đánh bóng văn phong Dataset (Ver 3)  
**Trạng thái:** 🔄 Đang tiến hành đánh bóng toàn bộ 600 dòng nguồn A_Dataset trong nền sử dụng đa luồng (2 workers).

---

## 🎯 NHIỆM VỤ ĐÃ HOÀN THÀNH
- Đã chạy full pipeline và sinh thành công distilled reasoning cho 1488 dòng.
- Đã lập báo cáo tổng quan tiến trình chạy tại [pipeline_v3_run_overview.md](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/docs/reports/ver2/pipeline_v3_run_overview.md).

### Lệnh chạy (copy & paste chính xác):

```powershell
$env:PYTHONIOENCODING='utf-8'
python src/reasoning_generation/ver_2/run_reasoning_pipeline_openrouter.py
```

> **Thư mục làm việc bắt buộc:**
> `d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method`

---

## 📋 THÔNG TIN KỸ THUẬT ĐỦ ĐỂ CHẠY

### Config Pipeline

| Thông số | Giá trị |
|----------|---------|
| Script chạy | `src/reasoning_generation/ver_2/run_reasoning_pipeline_openrouter.py` |
| Model | `tencent/hy3:free` via OpenRouter |
| API Key 1 | `.env → OPENROUTER_API_KEY` (đã có) |
| API Key 2 | `.env → OPENROUTER_API_KEY_2` (đã có) |
| N_WORKERS | **6** (3 workers/key, song song 2 keys) |
| Input CSV | `data/reasoning_generation/stratified_1488.csv` (1488 dòng) |
| Checkpoint JSON | `data/reasoning_generation/reasoning_generation_v3_log.json` |
| Output CSV | `data/final/final_distilled_reasoning_1488_v3.csv` |

### Pipeline Flow (3 Steps/Row)

```
Row [idx % 2 == 0 → Key_1 | idx % 2 == 1 → Key_2]

Step 1: Gen Answer
  Input : Q (câu hỏi tiếng Việt)
  Output: A_Cloud (câu trả lời, không reasoning flag)
  max_tokens = 1500

Step 2: Judge
  Input : Q + A_Dataset + A_Cloud
  Output: verdict JSON {"category": "...", "fact_check_notes": "..."}
  Categories: VERIFIED_EQUAL | CLOUD_SUPERIOR | DATASET_SUPERIOR | REJECTED
  max_tokens = 2500

Step 3: Reverse Prompting
  Input : Q + A_Final
          (A_Final = A_Cloud nếu VERIFIED_EQUAL/CLOUD_SUPERIOR)
          (A_Final = A_Dataset nếu DATASET_SUPERIOR)
          (skip nếu REJECTED)
  Output: Thinking_Reverse (100% tiếng Việt, 150-400 từ)
  max_tokens = 4000

Final response format:
  <think>
  {Thinking_Reverse}
  </think>
  {A_Final}
```

---

## 📊 KẾT QUẢ PILOT (3 DÒNG ĐÃ XÁC NHẬN)

| ID | Verdict | A_Final | Thinking chars | Chất lượng |
|----|---------|---------|---------------|-----------|
| 398 | DATASET_SUPERIOR | A_Dataset | 1170 | ✅ Sạch, tiếng Việt, mạch lạc |
| 8334 | CLOUD_SUPERIOR | A_Cloud | 1009 | ✅ Sạch, tiếng Việt, mạch lạc |
| 156 | DATASET_SUPERIOR | A_Dataset | 1289 | ✅ Sạch, tiếng Việt, mạch lạc |

---

## 🔄 CHECKPOINT SYSTEM (Quan Trọng!)

Pipeline đã có **checkpoint tự động** sau mỗi row hoàn thành:
- JSON log: `data/reasoning_generation/reasoning_generation_v3_log.json`
- CSV output: `data/final/final_distilled_reasoning_1488_v3.csv` (ghi lũy tiến)

**Nếu bị ngắt giữa chừng:** Chạy lại cùng lệnh — script sẽ tự đọc checkpoint và tiếp tục từ chỗ còn dang dở (skip các ID đã xử lý).

---

## ⚠️ LƯU Ý KHI THEO DÕI

### Dấu hiệu đang chạy tốt (stdout output):
```
[Start] ID=xxx | Key_1 | Tags: ...
[S1 ✓] ID=xxx A_Cloud=xxxc tokens=xxx
[S2 ✓] ID=xxx verdict=DATASET_SUPERIOR
[S3 ✓] ID=xxx Thinking=xxxc src=A_Dataset
--> [Tiến độ] xx/1488 (x.x%)
```

### Dấu hiệu có vấn đề:
- `[retry 1]` → bình thường, tự retry tối đa 3 lần
- `[S2 ✗]` hoặc `[S3 ✗]` → lỗi API, sẽ raise và script exit với code 1
- Script treo >5 phút không output → timeout, có thể kill và chạy lại (checkpoint sẽ giữ progress)

### Ước tính thời gian:
- ~30-60s/row (HY3 free tier latency)
- 6 workers song song → ~5-10 rows/phút
- **Tổng ước tính: 2-4 giờ**

---

## ✅ ĐỊNH NGHĨA "HOÀN THÀNH"

Pipeline hoàn tất khi output cuối cùng là:
```
======================================================================
   HOÀN THÀNH PIPELINE VER 3
======================================================================
Tổng đã xử lý: 1488
Log: data/reasoning_generation/reasoning_generation_v3_log.json
CSV: data/final/final_distilled_reasoning_1488_v3.csv

📊 VERDICT DISTRIBUTION:
  ✅ VERIFIED_EQUAL: xxx (xx.x%)
  🔄 CLOUD_SUPERIOR: xxx (xx.x%)
  📌 DATASET_SUPERIOR: xxx (xx.x%)
  🗑️ REJECTED: xxx (xx.x%)
```

**File cần kiểm tra sau khi xong:**
1. `data/final/final_distilled_reasoning_1488_v3.csv` — output SFT chính
2. `data/reasoning_generation/reasoning_generation_v3_log.json` — log chi tiết

---

## 📁 CẤU TRÚC THƯ MỤC LIÊN QUAN

```
project_root/
├── .env                                          ← API keys (đã có cả 2)
├── configs/paths.py                              ← Paths config
├── data/
│   ├── reasoning_generation/
│   │   ├── stratified_1488.csv                  ← INPUT (1488 dòng)
│   │   ├── reasoning_generation_v3_log.json     ← Checkpoint (tạo khi chạy)
│   │   └── pilot_run_v3_log.json                ← Log pilot đã có
│   └── final/
│       └── final_distilled_reasoning_1488_v3.csv ← OUTPUT SFT (tạo khi chạy)
└── src/reasoning_generation/ver_2/
    ├── run_reasoning_pipeline_openrouter.py      ← Script chạy chính ← ĐÂY
    ├── run_pilot_run_openrouter.py               ← Script pilot (đã xong)
    └── test_openrouter_connection.py             ← Test kết nối API
```
