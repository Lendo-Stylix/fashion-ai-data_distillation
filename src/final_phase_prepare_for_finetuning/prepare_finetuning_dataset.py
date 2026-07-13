import os
import pandas as pd
import json

csv_in_path = r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\final_distilled_reasoning_1488_v3.csv"
csv_out_path = r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\final_distilled_reasoning_1488_v3_grouped.csv"
jsonl_out_path = r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\final_distilled_reasoning_1488_v3_chatml.jsonl"

print("Step 1: Reading input CSV...")
df = pd.read_csv(csv_in_path)
print(f"Loaded {len(df)} rows.")

print("Step 2: Sorting by batch_id and ID...")
df_sorted = df.sort_values(by=['batch_id', 'ID']).reset_index(drop=True)

print(f"Step 3: Writing sorted CSV to {csv_out_path}...")
df_sorted.to_csv(csv_out_path, index=False, encoding='utf-8')
print("Sorted CSV written successfully.")

print("Step 4: Converting to ChatML JSONL format...")
system_prompt = "Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt một cách chuyên nghiệp"

with open(jsonl_out_path, 'w', encoding='utf-8') as f:
    for idx, row in df_sorted.iterrows():
        sample = {
            "conversations": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": str(row['question']).strip()
                },
                {
                    "role": "assistant",
                    "content": str(row['final_response']).strip()
                }
            ]
        }
        f.write(json.dumps(sample, ensure_ascii=False) + "\n")

print(f"Step 5: ChatML JSONL written to {jsonl_out_path}")
print("Preprocessing completed!")
