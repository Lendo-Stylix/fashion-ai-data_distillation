# Kế hoạch chuẩn bị Dataset và Chiến lược Fine-tuning Qwen 3.5

Kế hoạch này giúp gom nhóm dữ liệu theo `batch_id`, chuyển đổi định dạng dataset sang JSONL (ChatML) chuẩn và đề xuất các thông số fine-tune tối ưu để bảo tồn khả năng suy luận (reasoning) dựa trên các nghiên cứu trong `/docs/research/`.

## Phân tích hiện trạng Dataset
Qua kiểm tra dữ liệu hiện tại trong file `final_distilled_reasoning_1488_v3.csv`:
- **Tổng số dòng:** 1488 dòng (đầy đủ, không có dòng Null).
- **Chất lượng định dạng:** 100% các dòng đều có cấu trúc câu trả lời bắt đầu bằng thẻ `<think>` và kết thúc bằng `</think>`, theo sau là câu trả lời đã được chưng cất và đánh bóng.
- **Phân bố Batch ID:** Có 93 batch_id khác nhau. Thiết kế gốc ở Giai đoạn 5 (được mô tả trong [phase5_part1_stratified_batching_report.md](file: /docs/reports/phase5_part1_stratified_batching_report.md)) sử dụng thuật toán *Priority-based Fixed-Size Batching* để gom đúng 16 dòng thành một batch phân bổ stratified hoàn hảo theo tỷ lệ Tag nhằm chống dao động Gradient (Gradient Oscillation) khi train trên GPU. Do cơ chế ghi đa luồng bất đồng bộ của pipeline sinh reasoning, các dòng có cùng `batch_id` hiện đang bị xáo trộn rải rác. Chúng ta bắt buộc phải đọc file dữ liệu này và sắp xếp để gom nhóm các hàng theo đúng `batch_id` vật lý ban đầu.
- **Lỗi Parse:** Không còn bất kỳ dòng nào bị nhãn `PARSE_ERROR` hay `REJECTED` (đã được giải cứu sạch sẽ).

## Đề xuất Thay đổi

### 1. Gom nhóm batch_id và Chuyển đổi định dạng (Preprocessing)
Chúng ta sẽ xây dựng một script chuẩn bị dữ liệu `prepare_finetuning_dataset.py` để:
1. Đọc file CSV gốc.
2. Sắp xếp (sort) lại dữ liệu theo `batch_id` tăng dần, và `ID` tăng dần. Điều này giúp các hàng có cùng `batch_id` được gom nhóm đi liền kề nhau như mong muốn của bạn.
3. Ghi ra file CSV đã gom nhóm: `data/final/final_distilled_reasoning_1488_v3_grouped.csv`.
4. Chuyển đổi dữ liệu sang định dạng **JSONL ChatML** chuẩn để nạp trực tiếp vào các framework fine-tuning (Unsloth, LLaMA-Factory). Cấu trúc mỗi line:
   ```json
   {
     "conversations": [
       {
         "role": "system",
         "content": "Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt một cách chuyên nghiệp"
       },
       {
         "role": "user",
         "content": "Câu hỏi thời trang..."
       },
       {
         "role": "assistant",
         "content": "<think>\nLuồng suy luận nội tâm bằng tiếng Việt...\n</think>\nCâu trả lời cuối cùng..."
       }
     ]
   }
   ```
   *Lưu ý xử lý Assistant content:* Thẻ `<think>` và `</think>` được bọc trực tiếp trong phần nội dung của `assistant`. Đây là định dạng chuẩn của các mô hình Reasoning (đặc biệt khi kết hợp với Unsloth). Unsloth sẽ sử dụng `apply_chat_template` để sinh cột `text` huấn luyện từ cấu trúc `conversations` này.
5. Ghi ra file JSONL: `data/final/final_distilled_reasoning_1488_v3_chatml.jsonl`.

### 2. Chiến lược Fine-tuning Qwen 3.5 (4B) với Unsloth
Dựa trên tài liệu nghiên cứu `/docs/research/Qwen3.5_FineTune_Research.md` và kết quả đo lường token thực tế của bộ dữ liệu (sử dụng Tokenizer của Qwen2.5/3.5), chúng ta đề xuất cấu hình huấn luyện tối ưu cho phần cứng **2xT4 GPU** trên Kaggle như sau:

#### Phân tích Token thực tế của Dataset (1488 dòng):
- **Mean token length:** 678.30 tokens
- **Max token length:** 1196 tokens
- **90th percentile (p90):** 792.00 tokens
- **95th percentile (p95):** 858.65 tokens
- **99th percentile (p99):** 1056.26 tokens

**Kết luận về Max Seq Length:** Mốc 95% độ dài token là ~859 tokens. Do đó, khuyến nghị thiết lập `max_seq_length = 1024` (bao phủ ~98.5% tập dữ liệu) hoặc `1280` (bao phủ 100% dòng dài nhất). Thiết lập này giúp tiết kiệm đáng kể VRAM và tăng tốc độ huấn luyện trên 2xT4 GPU so với việc đặt 3072 hoặc 4096.

#### Đề xuất 2 Phiên bản Thử nghiệm (A/B Testing):
- **Version 1 (DoRA 8/16):** Thiết lập $r = 8$, $\alpha = 16$ (Bảo thủ, ít thay đổi trọng số gốc, bảo tồn khả năng suy luận tối đa).
- **Version 2 (DoRA 16/32):** Thiết lập $r = 16$, $\alpha = 32$ (Cho phép mô hình học sâu hơn kiến thức thời trang mới).

| Tham số | Giá trị Đề xuất | Lý do / Ý nghĩa |
| :--- | :--- | :--- |
| **Framework** | **Unsloth** | Tối ưu tốc độ, tiết kiệm VRAM trên Kaggle 2xT4. |
| **PEFT Method** | **DoRA** (`use_dora = True`) | DoRA tách biệt độ lớn và hướng của trọng số, giúp bảo tồn tư duy CoT tốt hơn LoRA. |
| **Rank & Alpha** | Thử nghiệm 2 bản:<br>1. $r = 8$, $\alpha = 16$<br>2. $r = 16$, $\alpha = 32$ | So sánh mức độ suy giảm khả năng suy luận và mức độ thuộc bài thời trang. |
| **Target Modules** | `all-linear` | Cập nhật tất cả các linear projection layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`). |
| **Loss Masking** | `DataCollatorForCompletionOnlyLM` | **Bắt buộc**. Chỉ tính loss trên phần trả lời của Assistant (bao gồm cả suy luận `<think>`). |
| **Response Template**| `"<|im_start|>assistant\n"` | Khớp với template ChatML của Qwen để định vị vùng tính loss. |
| **Max Seq Length** | **1024** (hoặc **1280**) | Mốc 95% là 859 tokens, 1024 giúp tối ưu hóa bộ nhớ đệm và tốc độ. |
| **Learning Rate** | $1 \times 10^{-4}$ đến $2 \times 10^{-4}$ | Learning Rate chuẩn cho LoRA/DoRA đối với bản 4B. |
| **Epochs** | 3 | Tránh overfit và đảm bảo hội tụ tốt trên tập dữ liệu 1488 dòng. |

---

## Chi tiết các File thay đổi

### [NEW] [prepare_finetuning_dataset.py](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/src/final_phase_prepare_for_finetuning/prepare_finetuning_dataset.py)
Tạo file script Python để thực hiện gom nhóm và chuyển đổi định dạng dữ liệu (CSV & JSONL ChatML).

### [NEW] [verify_finetuning_dataset.py](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/src/final_phase_prepare_for_finetuning/verify_finetuning_dataset.py)
Tạo file script Python để kiểm thử tự động, xác thực định dạng và phân bổ stratified tag trong batch.

### [NEW] [train_v1.py](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/src/final_phase_prepare_for_finetuning/train_v1.py)
Script Python huấn luyện Phiên bản 1 ($r=8, \alpha=16$) trên Kaggle Account 1.

### [NEW] [train_v2.py](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/src/final_phase_prepare_for_finetuning/train_v2.py)
Script Python huấn luyện Phiên bản 2 ($r=16, \alpha=32$) trên Kaggle Account 2.

### [NEW] [final_distilled_reasoning_1488_v3_grouped.csv](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/data/final/final_distilled_reasoning_1488_v3_grouped.csv)
File CSV mới sau khi đã gom nhóm theo `batch_id` và `ID`.

### [NEW] [final_distilled_reasoning_1488_v3_chatml.jsonl](file:///d:/FPT/Ki_V/DPL302m/group_project/template_discovery%26new-fine-tune-method/data/final/final_distilled_reasoning_1488_v3_chatml.jsonl)
File dataset định dạng JSONL (ChatML) chuẩn bị cho quá trình training.

---

## Cấu trúc Notebook Fine-tuning Unsloth trên Kaggle (2xT4 GPU)
Dưới đây là thiết kế các block code của Notebook giúp bạn copy-paste và chạy ổn định trên Kaggle:

### Cell 1: Cài đặt thư viện
```python
# Cài đặt Unsloth và xformers/trl tương thích
!pip install unsloth
!pip install --no-deps xformers trl peft accelerate bitsandbytes
```

### Cell 2: Đăng nhập Hugging Face
```python
from huggingface_hub import login
# Điền token write của bạn vào đây
login(token="YOUR_HF_WRITE_TOKEN")
```

### Cell 3: Tải Model Qwen 3.5 (4B) và Cấu hình PEFT DoRA
```python
from unsloth import FastLanguageModel
import torch

max_seq_length = 1024 # Hoặc 1280 tùy theo lựa chọn
dtype = None
load_in_4bit = True # Ép cân 4-bit giúp chạy mượt trên T4

# 1. Tải model gốc Qwen 3.5 và tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit", # Hoặc bản 3B/14B/Qwen 3.5 tương ứng
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# 2. Gắn PEFT Adapter (sử dụng DoRA)
model = FastLanguageModel.get_peft_model(
    model,
    r = 8,          # Đổi thành 16 cho Version 2
    lora_alpha = 16, # Đổi thành 32 cho Version 2
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    use_dora = True, # Kích hoạt DoRA bảo tồn khả năng reasoning
)
```

### Cell 4: Nạp và Map dữ liệu ChatML
```python
from datasets import load_dataset

# Nạp file JSONL đã convert
dataset = load_dataset("json", data_files="/kaggle/input/final_distilled_reasoning_1488_v3_chatml.jsonl", split="train")

def format_chat(row):
    # Dùng apply_chat_template của tokenizer Qwen để tạo cột 'text'
    row["text"] = tokenizer.apply_chat_template(row["conversations"], tokenize=False)
    return row

dataset = dataset.map(format_chat)
```

### Cell 5: Thiết lập Trainer (Loss Masking) và Huấn luyện
```python
from trl import SFTTrainer, SFTConfig
from transformers import DataCollatorForCompletionOnlyLM

# Thiết lập Loss Masking chỉ tính loss trên câu trả lời của Assistant
response_template = "<|im_start|>assistant\n"
collator = DataCollatorForCompletionOnlyLM(
    response_template=response_template, 
    tokenizer=tokenizer
)

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    data_collator = collator,
    dataset_num_proc = 2,
    args = SFTConfig(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        learning_rate = 1e-4,
        logging_steps = 10,
        num_train_epochs = 3,
        optim = "adamw_8bit",
        seed = 3407,
        output_dir = "qwen-fashion-checkpoints",
        
        # Sao lưu an toàn
        save_strategy = "steps",
        save_steps = 50,
        save_total_limit = 2,
        push_to_hub = True,
        hub_model_id = "YOUR_USERNAME/qwen-3.5-fashion-fit",
        hub_strategy = "checkpoint",
    ),
)

trainer_stats = trainer.train()
```

---

## Kế hoạch Xác minh (Verification Plan)

Để đảm bảo dữ liệu sau xử lý giữ nguyên vẹn cấu trúc và triết lý Stratified Batching đã thiết kế ở Giai đoạn 5, chúng ta sẽ thực hiện quy trình kiểm thử chi tiết sau:

### Kiểm thử Tự động (Automated Verification)
Chúng ta sẽ tích hợp các kiểm tra (assertions) trực tiếp vào script `prepare_finetuning_dataset.py` hoặc viết script kiểm tra riêng để xác thực các tiêu chí:
1. **Kiểm tra Tổng số dòng:** Xác thực file CSV mới và file JSONL có đúng **1488 dòng** dữ liệu (khớp 100% dữ liệu gốc).
2. **Kiểm tra Gom nhóm vật lý (Contiguous Grouping):** Đảm bảo các dòng có cùng `batch_id` nằm liên tục cạnh nhau. Nếu giá trị `batch_id` thay đổi (chuyển sang batch tiếp theo), nó tuyệt đối không được xuất hiện lại ở các dòng phía sau.
3. **Kiểm tra Kích thước Batch cố định:** Đảm bảo mỗi `batch_id` (từ 1 đến 93) chứa **đúng 16 dòng** dữ liệu liên tiếp, không dư không thiếu.
4. **Xác thực Tính Stratified (Phân bổ Tag):** Trích xuất tỷ lệ Tag chính (Primary Tag) trong từng Batch sau khi sắp xếp để đối chiếu so sánh với phân bổ gốc của toàn bộ dataset (đảm bảo mỗi batch 16 dòng đều chứa các tag lớn nhỏ theo đúng tỷ lệ thiết kế để ngăn Gradient Oscillation).
5. **Kiểm tra Định dạng JSONL ChatML:**
   - Mỗi dòng phải là một JSON object hợp lệ.
   - Có cấu trúc key `conversations` chứa đúng 3 phần tử theo thứ tự: `system`, `user`, và `assistant`.
   - `content` của `role: system` phải khớp chính xác: `"Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt một cách chuyên nghiệp"`.
   - `content` của `role: assistant` bắt buộc phải bắt đầu bằng thẻ `<think>\n` và chứa thẻ đóng `\n</think>` phân tách rõ ràng với câu trả lời thời trang thực tế.
6. **Kiểm tra Mã hóa File:** File JSONL đầu ra phải được lưu dưới dạng **UTF-8 không BOM** để không bị lỗi font tiếng Việt khi nạp vào Unsloth.

### Kiểm thử Thủ công (Manual Inspection)
- Trích xuất ngẫu nhiên **1 Batch hoàn chỉnh (16 dòng)** của một `batch_id` bất kỳ để kiểm tra trực tiếp:
  - Cấu trúc Tag phân bổ trong Batch đó có đa dạng và xen kẽ đúng như report Stratified Batching không.
  - Định dạng hiển thị của thẻ `<think>` và nội dung trả lời của Assistant có hiển thị đẹp, rõ ràng và không bị vỡ định dạng hay không.
