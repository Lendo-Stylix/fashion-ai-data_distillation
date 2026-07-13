import pandas as pd
import numpy as np
from transformers import AutoTokenizer
import os

csv_path = r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\final_distilled_reasoning_1488_v3.csv"

# Load data
df = pd.read_csv(csv_path)

print("Loading tokenizer Qwen/Qwen2.5-7B-Instruct...")
try:
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct", trust_remote_code=True)
except Exception as e:
    print(f"Error loading online tokenizer: {e}")
    print("Trying local fallback or character estimation...")
    tokenizer = None

system_prompt = "Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt một cách chuyên nghiệp"

token_lengths = []

for idx, row in df.iterrows():
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": str(row['question'])},
        {"role": "assistant", "content": str(row['final_response'])}
    ]
    
    if tokenizer is not None:
        try:
            # apply_chat_template
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            tokens = tokenizer.encode(text)
            token_lengths.append(len(tokens))
        except Exception as e:
            text = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{row['question']}<|im_end|>\n<|im_start|>assistant\n{row['final_response']}<|im_end|>"
            word_count = len(text.split())
            token_lengths.append(int(word_count * 1.5))
    else:
        text = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{row['question']}<|im_end|>\n<|im_start|>assistant\n{row['final_response']}<|im_end|>"
        word_count = len(text.split())
        token_lengths.append(int(word_count * 1.5))

token_lengths = np.array(token_lengths)

# Calculate statistics
mean_len = np.mean(token_lengths)
max_len = np.max(token_lengths)
p90 = np.percentile(token_lengths, 90)
p95 = np.percentile(token_lengths, 95)
p99 = np.percentile(token_lengths, 99)

print(f"\n--- TOKEN LENGTH STATISTICS (Qwen-style) ---")
print(f"Mean token length: {mean_len:.2f}")
print(f"Max token length: {max_len}")
print(f"90th percentile: {p90:.2f}")
print(f"95th percentile (p95): {p95:.2f}")
print(f"99th percentile: {p99:.2f}")

# Save token lengths to file for confirmation
df['token_length'] = token_lengths
df.to_csv(r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\final_distilled_reasoning_1488_v3_tokenized.csv", index=False)
print("Saved analysis data to final_distilled_reasoning_1488_v3_tokenized.csv")
