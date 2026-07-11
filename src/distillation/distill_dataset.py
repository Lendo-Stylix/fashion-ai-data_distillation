import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from configs import paths

import pandas as pd
import re

print("Loading datasets...")
df_eval = pd.read_csv(paths.EVALUATED_CSV)
df_data = pd.read_csv(paths.CLEANED_10K_CSV)

df_eval['index'] = df_eval['ID'] - 1
df_merged = pd.merge(df_eval, df_data, left_on='index', right_index=True)

print(f"Total rows: {len(df_merged)}")

# --- STEP 1: DEITA Quality & Complexity Filter ---
df_deita = df_merged[(df_merged['Difficulty'] >= 2) & (df_merged['Detail'] == 3) & (df_merged['Vocab'] >= 2)]
print(f"Rows after DEITA Filter (Hard=2+, Detail=3, Vocab=2+): {len(df_deita)}")

if len(df_deita) < 1500:
    print("Relaxing detail constraint to Detail >= 2...")
    df_deita = df_merged[(df_merged['Difficulty'] >= 2) & (df_merged['Detail'] >= 2) & (df_merged['Vocab'] >= 2)]
    print(f"Rows after Relaxed DEITA Filter: {len(df_deita)}")

# --- BỎ QUA STEP 2: Translation Quality Filter (Sẽ không xóa data ở đây nữa) ---
df_clean = df_deita.copy()
print(f"Skipping Layer 1 Regex dropping. Retaining all {len(df_clean)} DEITA-Quality rows.")

# --- STEP 3: DEITA Diversity (Stratified Sampling) ---
minorities = ['Làm đẹp & Chăm sóc cá nhân', 'Phong thái & Tâm lý', 'Mua sắm & Quản lý tủ đồ', 'Bảo quản & Thời trang bền vững', 'Phong cách sống']

def contains_minority(tags):
    tag_list = [t.strip() for t in str(tags).split(',')]
    for t in tag_list:
        if t in minorities:
            return True
    return False

df_minority = df_clean[df_clean['Tags'].apply(contains_minority)]
df_majority = df_clean[~df_clean['Tags'].apply(contains_minority)]

print(f"Found {len(df_minority)} minority rows and {len(df_majority)} majority rows.")

TARGET_SIZE = 1500
minority_size = len(df_minority)
majority_needed = TARGET_SIZE - minority_size

if majority_needed > 0:
    if majority_needed > len(df_majority):
        majority_needed = len(df_majority)
    df_sampled_majority = df_majority.sample(n=majority_needed, random_state=42)
    df_final = pd.concat([df_minority, df_sampled_majority])
else:
    df_final = df_minority.sample(n=TARGET_SIZE, random_state=42)

df_final = df_final.sort_values(by='ID').reset_index(drop=True)
print(f"FINAL Pre-Audit Dataset Size: {len(df_final)}")

output_path = paths.DATA_PROCESSED / 'distilled_1500_pre_audit.csv'
df_final.to_csv(output_path, index=False)
print(f"Saved to {output_path}")

df_final['Tags_List'] = df_final['Tags'].apply(lambda x: [tag.strip() for tag in str(x).split(',')])
df_exploded = df_final.explode('Tags_List')
print("\nFinal Tag Distribution:")
print(df_exploded['Tags_List'].value_counts())
