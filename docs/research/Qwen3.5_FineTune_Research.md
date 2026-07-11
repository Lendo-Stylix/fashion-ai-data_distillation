# Nghiên cứu chuyên sâu: Fine-tune mô hình Qwen 3.5 (4B)

Tài liệu này tổng hợp các nghiên cứu về cấu trúc Chat Template, định dạng Dataset và các phương pháp Fine-tune (đặc biệt là LoRA) nhằm bảo tồn khả năng suy luận (reasoning) và tránh hiện tượng học vẹt (catastrophic forgetting) trên dòng mô hình Qwen 3.5.

## 1. Chat Template của Qwen 3.5

Qwen 3.5 sử dụng định dạng **ChatML** thông qua Jinja template. Việc định dạng sai template là nguyên nhân hàng đầu khiến mô hình hoạt động kém sau khi fine-tune.

- **Cấu trúc cơ bản:** Sử dụng các token đặc biệt `<|im_start|>` và `<|im_end|>` để phân tách vai trò (system, user, assistant).
- **Khả năng suy luận (Reasoning/Thinking):** Các phiên bản Qwen mới (đặc biệt có khả năng reasoning) hỗ trợ các thẻ `<think>...</think>`. Đối với các task cần suy luận sâu, model sẽ tạo ra chuỗi suy luận bên trong thẻ `<think>` trước khi đưa ra câu trả lời cuối cùng.
- **Tool Calling:** Hỗ trợ gọi hàm thông qua thẻ `<tool_call>...</tool_call>`.

**Lưu ý:** Nếu bạn dùng `llama.cpp` hoặc vLLM, đảm bảo file `tokenizer_config.json` chứa Jinja template chính xác. Đôi khi template mặc định trên HuggingFace bị lỗi khoảng trắng khiến model sinh ra vô tận hoặc loạn ngôn. Cần sử dụng các phiên bản chat template đã fix (ví dụ tìm kiếm repo `froggeric/Qwen-Fixed-Chat-Templates`).

## 2. Định dạng Dataset chuẩn (Bảo tồn khả năng Reasoning)

Bạn đề cập rằng khi fine-tune thuần Q&A (Hỏi - Đáp), mô hình bị phá trọng số và mất đi khả năng reasoning. Đây là hiện tượng đặc biệt nghiêm trọng ở các mô hình có khả năng tư duy chuỗi (Chain of Thought).

Nguyên nhân: Khi train bằng dataset thuần Q&A (chỉ có câu hỏi và đáp án trực tiếp), quá trình tính loss ép mô hình phải "đi tắt" từ câu hỏi tới luôn câu trả lời mà bỏ qua bước suy luận trung gian. Trọng số của mô hình bị điều chỉnh để ngừng suy nghĩ (unlearn reasoning).

### Cấu trúc Dataset tối ưu
Dataset phải là dạng hội thoại (Conversational format) và **bắt buộc phải có bước suy luận** trong câu trả lời của Assistant.

Định dạng JSONL (phổ biến trong SFTTrainer, Unsloth):
```json
[
  {
    "conversations": [
      {
        "role": "system",
        "content": "Bạn là một chuyên gia. Hãy suy luận từng bước một cách chi tiết trước khi đưa ra câu trả lời cuối cùng."
      },
      {
        "role": "user",
        "content": "Câu hỏi chuyên ngành hoặc tình huống của bạn ở đây?"
      },
      {
        "role": "assistant",
        "content": "<think>\n1. Phân tích yêu cầu bài toán...\n2. Liên kết với kiến thức mảng A...\n3. Đánh giá các trường hợp ngoại lệ...\n4. Rút ra kết luận...\n</think>\nĐây là câu trả lời trực tiếp và súc tích dành cho bạn..."
      }
    ]
  }
]
```

**Nguyên tắc xử lý Data:**
1. **Distillation để tạo bước suy luận:** Đừng dùng data Q&A cũ. Hãy dùng một mô hình lớn (như GPT-4o, Claude 3.5 Sonnet) để sinh lại data. Cung cấp cho GPT-4o cặp Q&A của bạn và prompt: *"Dựa vào câu hỏi và đáp án này, hãy sinh ra một quá trình suy luận nội tâm chi tiết đặt trong thẻ `<think>...</think>` trước khi đưa ra câu trả lời."*
2. **Loss Masking (Chỉ tính Loss trên phần trả lời):** Đảm bảo script training của bạn có sử dụng kỹ thuật che Loss (ví dụ `DataCollatorForCompletionOnlyLM` của thư viện `trl`). Mô hình không được học cách sinh ra prompt của User hay System.

## 3. Khắc phục Catastrophic Forgetting bằng Hyperparameter Tuning

Do giới hạn về khả năng đánh giá Data Mixture ở thời điểm hiện tại, chiến lược an toàn và tối ưu nhất để bảo tồn khả năng suy luận là **kiểm soát chặt chẽ bộ siêu tham số (hyperparameters)**. Các thông số này sẽ được dùng để demo trên bản 4B và là cơ sở thiết yếu để bạn scale lên 9B.

### A. Tối ưu quá trình Training (DataCollator & Dataset)
- **`DataCollatorForCompletionOnlyLM`**: Đây là yếu tố **sống còn**. Nếu không dùng kỹ thuật này, mô hình sẽ tính Loss trên cả câu hỏi của người dùng, dẫn đến việc mô hình học sai định hướng.
  - *Sử dụng với Qwen (ChatML)*: Phải set chính xác `response_template="<|im_start|>assistant\n"`. Lưu ý kiểm tra kỹ token ID sau khi parse để đảm bảo nó khớp với tokenizer của bạn.
- **`train_dataset length` (Kích thước tập dữ liệu)**: Số lượng không bằng chất lượng. Không cần dataset quá lớn, chỉ cần 1.000 - 5.000 samples cực kỳ chuẩn xác (bắt buộc phải có thẻ `<think>`). Tập data quá lớn nhưng thiếu `<think>` sẽ ngay lập tức "xóa sổ" khả năng reasoning của mô hình.
- **`max_seq_length`**: Phải cấu hình đủ dài để chứa trọn vẹn: Prompt + phần `<think>` (thường rất dài) + phần trả lời. Khuyến nghị đặt mức **2048 đến 4096**. Nếu đặt ngắn, bước suy luận bị cắt cụt giữa chừng sẽ làm quá trình training đổ vỡ.

### B. Tối ưu Cấu hình PEFT (LoRA / DoRA)
- **`use_dora`**: **Bắt buộc nên kích hoạt (`True`)**. DoRA (Weight-Decomposed Low-Rank Adaptation) rã trọng số thành 2 vector độc lập (Độ lớn và Hướng). Nghiên cứu chỉ ra DoRA "thông minh" hơn LoRA rất nhiều trong việc học task mới mà **không phá hỏng tư duy nền tảng**. Việc dùng DoRA sẽ bù đắp hoàn hảo cho việc bạn không thể dùng Data Mixture.
- **`rank` ($r$)**: Khởi đầu với **$r = 8$** hoặc **$r = 16$**. Tuyệt đối không ham rank cao (64, 128) khi bạn đang đánh giá mức độ forgetting. Rank càng thấp, lượng kiến thức cũ bị ghi đè càng ít.
- **`lora_alpha`**: Thông số scale của LoRA. Tiêu chuẩn tốt nhất là đặt **$lora\_alpha = 2 \times r$** (ví dụ: $r=8$, $alpha=16$).
- **`target_modules`**: Để model thích nghi tốt, set thành **`all-linear`** (sẽ fine-tune tất cả các projection layers của Attention và MLP: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`). Nếu bản demo 4B vẫn có dấu hiệu mất suy luận, hãy giảm scope xuống chỉ còn `["q_proj", "v_proj"]`.

### C. Định hướng Scale từ 4B lên 9B (Learning Rate & Epoch)
Khi bạn có được bộ tham số ổn định từ 4B và muốn vác lên 9B, điều cần quan tâm nhất là **Learning Rate** và VRAM.

- **`learning_rate` (LR)**: 
  - **Trên bản demo 4B**: Mức an toàn thường là **$1 \times 10^{-4}$** đến **$2 \times 10^{-4}$**.
  - **Scale lên 9B**: Khi chạy model 9B, VRAM sẽ bị chiếm dụng nhiều hơn, ép bạn phải **giảm Batch Size**. Quy luật bất thành văn: **Batch Size giảm thì Learning Rate BẮT BUỘC phải giảm theo**. Để an toàn khi train 9B, hãy chủ động hạ LR xuống mức **$1 \times 10^{-5}$** đến **$5 \times 10^{-5}$**. Luôn đính kèm Cosine Learning Rate Scheduler và Warmup (khoảng 5-10% tổng số steps).
- **`num_train_epochs`**: Giữ ở mức **3 đến 5 epochs**. Nếu dataset của bạn nhỏ và chất lượng cao, chạy quá 5 epoch sẽ gây overfitting ngay lập tức.
