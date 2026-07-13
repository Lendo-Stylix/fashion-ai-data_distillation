# Báo cáo Điều chỉnh Cấu hình Fine-tuning Qwen 3.5 (4B)

Tài liệu này ghi nhận và phân tích các thay đổi cấu hình fine-tuning từ kế hoạch ban đầu sang cấu hình chạy thực tế ổn định trên Kaggle thu thập từ 2 file notebook mới.

---

## 1. Các điểm thay đổi cốt lõi trong cấu hình

### a) Thay đổi Mô hình Gốc (Base Model)
* **Kế hoạch ban đầu:** Đề xuất sử dụng dòng `Qwen3.5-4B-Instruct`.
* **Cấu hình thực tế hoạt động:** Thay thế hoàn chỉnh bằng **`techwithsergiu/Qwen3.5-text-4B-bnb-4bit`**.
* **Phân tích:** 
  - Bản Qwen 3.5-text-4B-bnb-4bit gọn nhẹ và tiết kiệm tài nguyên GPU T4 và băng thông mạng cho tài khoản Kaggle.
  - Phiên bản đóng gói BnB 4-bit của tác giả techwithsergiu có số lượt tải về lớn nhất trong dòng qwen3.5-4b-bnb.

### b) Không sử dụng DoRA (Weight-Decomposed LoRA) — Chuyển sang LoRA thông thường
* **Kế hoạch ban đầu:** Đề xuất sử dụng DoRA (`use_dora = True`) để phân tách độ lớn và hướng trọng số nhằm bảo tồn khả năng suy luận (CoT) tốt hơn.
* **Cấu hình thực tế hoạt động:** Quay lại sử dụng **LoRA truyền thống** (không cấu hình `use_dora=True`, mặc định là `False`).
* **Lý do điều chỉnh:** 
  - Thư viện Unsloth hiện tại khi kết hợp các custom kernels tăng tốc (như triton) với mô hình lượng tử hóa 4-bit (`load_in_4bit = True`) và Gradient Checkpointing (`use_gradient_checkpointing = "unsloth"`) sẽ bị crash trong quá trình lan truyền ngược (backward pass) nếu kích hoạt DoRA.
  - Chuyển đổi về LoRA thường giúp quá trình huấn luyện diễn ra ổn định tuyệt đối trên GPU T4, đồng thời giữ nguyên tốc độ huấn luyện siêu tốc đặc trưng của Unsloth.

### c) Thay đổi cơ chế Loss Masking (Che Loss)
* **Kế hoạch ban đầu:** Đề xuất sử dụng `DataCollatorForCompletionOnlyLM` của Hugging Face `transformers` để chỉ tính loss trên câu trả lời của Assistant.
* **Cấu hình thực tế hoạt động:** Sử dụng hàm helper tích hợp của Unsloth:
  ```python
  from unsloth.chat_templates import train_on_responses_only
  trainer = train_on_responses_only(
      trainer,
      instruction_part = "<|im_start|>user\n",
      response_part = "<|im_start|>assistant\n",
  )
  ```
* **Lý do điều chỉnh:** 
  - Tránh các lỗi tokenizer split không khớp (misalignment) của Hugging Face khi xử lý các ký tự xuống dòng `\n` và tag đặc biệt của ChatML (`<|im_start|>` và `<|im_end|>`).
  - Hàm helper của Unsloth thực hiện gán nhãn `-100` cho phần prompt một cách chính xác và hiệu quả hơn.

---

## 2. Bảng tổng hợp so sánh thông số

| Tham số | Thiết kế ban đầu | Cấu hình thực tế hoạt động |
| :--- | :--- | :--- |
| **Base Model** | `unsloth/Qwen3.5-4B-Instruct` | `techwithsergiu/Qwen3.5-text-4B-bnb-4bit` |
| **PEFT Method** | DoRA (`use_dora = True`) | LoRA (`use_dora = False`) |
| **Max Seq Length** | 1280 | 1280 |
| **Loss Masking** | `DataCollatorForCompletionOnlyLM` | `train_on_responses_only` (Unsloth) |
| **Learning Rate** | $1 \times 10^{-4}$ | $1 \times 10^{-4}$ |
| **Epochs** | 3 | 3 |
| **W&B Logging** | Không bắt buộc | Tích hợp (Project: `locvu0309-fpt-university`) |
