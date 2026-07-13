import pandas as pd
from collections import defaultdict
import sys
import os

# Đảm bảo có thể import configs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from configs.paths import ROOT, DATA_REASONING, STRATIFIED_CSV

def main():
    # Sửa lỗi Unicode khi in tiếng Việt trên terminal Windows
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Đọc file có header
    input_file = ROOT / "data" / "isolated_proofs" / "distilled_1488_perfect.csv"
    
    print(f"Reading from {input_file}...")
    df = pd.read_csv(input_file)
    
    # Cột 'Tags' chứa tags (vd: "Kiến thức cơ bản, Phong cách")
    tag_groups = defaultdict(list)
    
    for _, row in df.iterrows():
        tags_str = str(row['Tags'])
        # Lấy tag đầu tiên làm Primary Tag
        primary_tag = tags_str.split(',')[0].strip()
        tag_groups[primary_tag].append(row)
        
    print("\nTag Distribution Before Stratification:")
    for tag, rows in tag_groups.items():
        print(f"- {tag}: {len(rows)} rows")
        
    # Kích thước Batch thực tế lúc Fine-tune
    BATCH_SIZE = 16
    total_batches = (len(df) + BATCH_SIZE - 1) // BATCH_SIZE
    
    batches = [[] for _ in range(total_batches)]
    
    # Sắp xếp các tag theo số lượng giảm dần để phân bổ
    sorted_tags = sorted(tag_groups.keys(), key=lambda t: len(tag_groups[t]), reverse=True)
    
    import random
    random.seed(42) # Đảm bảo tái lập kết quả
    
    batch_idx = 0
    # Phân bổ rải đều (Perfect Stratified Distribution)
    for tag in sorted_tags:
        rows = tag_groups[tag]
        # Xáo trộn các câu trong cùng 1 tag để tăng tính ngẫu nhiên
        random.shuffle(rows)
        for row in rows:
            batches[batch_idx].append(row)
            batch_idx = (batch_idx + 1) % total_batches
            
    stratified_rows = []
    for i, batch in enumerate(batches):
        # Xáo trộn thứ tự các câu bên trong 1 batch để model không học vẹt thứ tự tag
        random.shuffle(batch)
        for row in batch:
            r = row.copy()
            r['batch_id'] = i + 1
            stratified_rows.append(r)
                
    # Ghi ra file
    df_stratified = pd.DataFrame(stratified_rows)
    
    DATA_REASONING.mkdir(parents=True, exist_ok=True)
    
    print(f"\nWriting to {STRATIFIED_CSV}...")
    df_stratified.to_csv(STRATIFIED_CSV, header=True, index=False)
    print(f"Done! Total rows: {len(df_stratified)}")

if __name__ == "__main__":
    main()
