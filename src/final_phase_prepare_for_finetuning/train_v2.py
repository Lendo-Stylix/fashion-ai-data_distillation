# %% [markdown]
# # CELL 1: Cài đặt Unsloth và các thư viện liên quan
# %%
!pip install unsloth
!pip install --no-deps xformers trl peft accelerate bitsandbytes

# %% [markdown]
# # CELL 2: Đăng nhập Hugging Face Hub (Cần token có quyền write)
# %%
from huggingface_hub import login
# Thay thế token Hugging Face của bạn vào đây
login(token="YOUR_HF_WRITE_TOKEN")

# %% [markdown]
# # CELL 3: Tải Model Qwen 3.5 và Cấu hình PEFT DoRA (Version 2: r=16, alpha=32)
# %%
from unsloth import FastLanguageModel
import torch

max_seq_length = 1280
dtype = None
load_in_4bit = True

# 1. Tải model gốc và tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# 2. Gắn PEFT Adapter (sử dụng DoRA)
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    lora_alpha = 32,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    use_dora = True, # Kích hoạt DoRA bảo tồn khả năng reasoning
)

# %% [markdown]
# # CELL 4: Nạp và Map dữ liệu ChatML
# %%
from datasets import load_dataset
import os

# Tự động nhận diện đường dẫn Kaggle Dataset hoặc local
kaggle_path = "/kaggle/input/final-distilled-reasoning-1488-v3-chatml/final_distilled_reasoning_1488_v3_chatml.jsonl"
local_path = "data/final/final_distilled_reasoning_1488_v3_chatml.jsonl"
if os.path.exists(kaggle_path):
    data_path = kaggle_path
else:
    data_path = local_path

dataset = load_dataset("json", data_files=data_path, split="train")

def format_chat(row):
    # Sử dụng template ChatML của Qwen
    row["text"] = tokenizer.apply_chat_template(row["conversations"], tokenize=False)
    return row

dataset = dataset.map(format_chat)

# %% [markdown]
# # CELL 5: Thiết lập Trainer với Loss Masking và Huấn luyện
# %%
from trl import SFTTrainer, SFTConfig
from transformers import DataCollatorForCompletionOnlyLM

# Thiết lập Loss Masking chỉ tính loss trên câu trả lời của Assistant (bao gồm cả thẻ <think>)
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
        output_dir = "qwen-fashion-r16-alpha32-checkpoints",
        
        # Cấu hình lưu trữ và đẩy lên HF Hub
        save_strategy = "steps",
        save_steps = 50,
        save_total_limit = 2,
        push_to_hub = True,
        hub_model_id = "YOUR_USERNAME/qwen-3.5-fashion-r16-alpha32",
        hub_strategy = "checkpoint",
    ),
)

trainer_stats = trainer.train()
