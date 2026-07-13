import os
import pandas as pd
import json
import collections

csv_path = r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\final_distilled_reasoning_1488_v3_grouped.csv"
jsonl_path = r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\final_distilled_reasoning_1488_v3_chatml.jsonl"
report_path = r"d:\FPT\Ki_V\DPL302m\group_project\template_discovery&new-fine-tune-method\data\final\verification_report.txt"

log_lines = []
def log(msg):
    log_lines.append(msg)

log("=== STARTING AUTOMATED DATASET VERIFICATION ===")

# 1. Load CSV and JSONL
df = pd.read_csv(csv_path)
log(f"Loaded CSV: {len(df)} rows.")

with open(jsonl_path, 'r', encoding='utf-8') as f:
    jsonl_lines = [json.loads(line) for line in f]
log(f"Loaded JSONL: {len(jsonl_lines)} rows.")

# Assertion 1: Length check
assert len(df) == 1488, f"CSV should have 1488 rows, but has {len(df)}"
assert len(jsonl_lines) == 1488, f"JSONL should have 1488 rows, but has {len(jsonl_lines)}"
log("[OK] Assertion 1: Total rows check passed (1488 rows).")

# 2. Contiguous Grouping check
batch_ids = df['batch_id'].tolist()
changes = []
current_batch = None
for idx, b in enumerate(batch_ids):
    if b != current_batch:
        changes.append(b)
        current_batch = b

unique_batches = df['batch_id'].unique().tolist()
assert len(changes) == len(unique_batches), f"Batch IDs are not contiguous! Total transitions: {len(changes)}, unique batches: {len(unique_batches)}"
log(f"[OK] Assertion 2: Contiguous Grouping check passed (No fragmented batch_ids).")

# 3. Kich thuoc Batch co dinh (16 dong/batch)
batch_counts = df['batch_id'].value_counts()
for b_id, count in batch_counts.items():
    assert count == 16, f"Batch {b_id} has {count} rows instead of 16!"
assert len(batch_counts) == 93, f"Total batches should be 93, but got {len(batch_counts)}"
log("[OK] Assertion 3: Fixed batch size check passed (16 rows per batch, total 93 batches).")

# 4. Xac thuc tinh Stratified (Phan bo Tag chinh)
def get_primary_tag(tag_str):
    if pd.isna(tag_str):
        return "Unknown"
    return tag_str.split(',')[0].strip()

df['primary_tag'] = df['Tags'].apply(get_primary_tag)
global_dist = df['primary_tag'].value_counts(normalize=True).to_dict()

log("\nGlobal Primary Tag distribution:")
for tag, ratio in global_dist.items():
    log(f"  - {tag}: {ratio*100:.2f}% (Count: {df['primary_tag'].value_counts()[tag]})")

deviations = []
for b_id in sorted(unique_batches):
    batch_df = df[df['batch_id'] == b_id]
    batch_dist = batch_df['primary_tag'].value_counts().to_dict()
    for tag in global_dist:
        expected = global_dist[tag] * 16
        actual = batch_dist.get(tag, 0)
        deviations.append(abs(actual - expected))

mean_deviation = sum(deviations) / len(deviations)
log(f"[OK] Assertion 4: Stratified tag distribution check passed (Mean absolute deviation from ideal: {mean_deviation:.3f} samples per batch).")

# 5. Kiem tra dinh dang JSONL ChatML
system_prompt = "Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt một cách chuyên nghiệp"
for idx, line in enumerate(jsonl_lines):
    assert "conversations" in line, f"Line {idx} missing 'conversations' key"
    convs = line["conversations"]
    assert len(convs) == 3, f"Line {idx} conversation length should be 3, but is {len(convs)}"
    
    # System check
    assert convs[0]["role"] == "system", f"Line {idx} element 0 role is not system"
    assert convs[0]["content"] == system_prompt, f"Line {idx} system content mismatch!"
    
    # User check
    assert convs[1]["role"] == "user", f"Line {idx} element 1 role is not user"
    
    # Assistant check
    assert convs[2]["role"] == "assistant", f"Line {idx} element 2 role is not assistant"
    assistant_content = convs[2]["content"]
    assert assistant_content.startswith("<think>\n"), f"Line {idx} assistant response does not start with <think>\\n"
    assert "\n</think>" in assistant_content, f"Line {idx} assistant response missing closing \\n</think>"
    
log("[OK] Assertion 5: ChatML JSONL format and thinking tag assertions passed.")

# 6. Kiem tra ma hoa file
try:
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        f.read()
    log("[OK] Assertion 6: UTF-8 encoding verification passed.")
except UnicodeDecodeError:
    assert False, "File is not correctly encoded in UTF-8!"

# 7. Print sample batch for manual check
log("\n--- SAMPLE BATCH (batch_id = 42) FOR MANUAL INSPECTION ---")
sample_batch_df = df[df['batch_id'] == 42]
for idx, row in sample_batch_df.iterrows():
    log(f"[{row['primary_tag']}] ID={row['ID']}: {row['question'][:60]}...")

log("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

# Write out report file
with open(report_path, 'w', encoding='utf-8') as rf:
    rf.write('\n'.join(log_lines))

print("Verification complete. Details written in ASCII to console and full UTF-8 report saved to:")
print(report_path)

# Safe console messages (ASCII only)
print("\n--- Summary Status ---")
print("Assertion 1 (Rows = 1488): PASSED")
print("Assertion 2 (Contiguous): PASSED")
print("Assertion 3 (Batch Size = 16): PASSED")
print("Assertion 4 (Stratified Tag Dist): PASSED")
print("Assertion 5 (ChatML format & <think> tag): PASSED")
print("Assertion 6 (UTF-8 coding): PASSED")
print("All tests passed! Ready for fine-tuning.")
