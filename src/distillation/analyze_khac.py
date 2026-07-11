import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from configs import paths

import pandas as pd

df_eval = pd.read_csv(paths.EVALUATED_CSV)
df_orig = pd.read_csv(paths.CLEANED_10K_CSV)
df_orig['ID'] = df_orig.index + 1
df = pd.merge(df_eval, df_orig, on='ID')
df_khac = df[df['Tags'].str.contains('Khác', na=False)]

pattern = '|'.join(['tự tin', 'tâm lý', 'cảm xúc', 'thoải mái', 'tư thế', 'ngôn ngữ cơ thể', 'phong thái', 'dáng đi', 'cử chỉ', 'tóc', 'kiểu tóc', 'màu tóc', 'cắt tóc', 'nước hoa', 'mùi hương', 'hương thơm', 'trang điểm', 'makeup', 'da', 'skincare'])

df_remaining = df_khac[~(df_khac['translated_input'].str.contains(pattern, case=False, na=False) | df_khac['translated_output'].str.contains(pattern, case=False, na=False))]

print(f'Remaining items: {len(df_remaining)}')
for _, row in df_remaining.head(15).iterrows():
    print(f"ID: {row['ID']}")
    print(f"Q: {row['translated_input']}")
    print('-'*30)
