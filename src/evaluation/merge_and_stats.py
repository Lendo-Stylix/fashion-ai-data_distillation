import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from configs import paths

import pandas as pd

print("Merging Phase 2 results...")
df_main = pd.read_csv(paths.EVALUATED_CSV)
df_phase2 = pd.read_csv(paths.DATA_PROCESSED / 'evaluated_dataset_phase2_temp.csv')

# Remove the old rows from main
df_main = df_main[~df_main['ID'].isin(df_phase2['ID'])]

# Append the new rows
df_main = pd.concat([df_main, df_phase2], ignore_index=True)

# Sort by ID
df_main = df_main.sort_values(by='ID').reset_index(drop=True)

# Save
df_main.to_csv(paths.EVALUATED_CSV, index=False)
print("Merge complete!")

print("-" * 50)
print("FINAL DATASET TAG DISTRIBUTION (10,000 ROWS)")
print("-" * 50)

# Explode tags
df_main['Tags_List'] = df_main['Tags'].apply(lambda x: [tag.strip() for tag in str(x).split(',')])
df_exploded = df_main.explode('Tags_List')
tag_counts = df_exploded['Tags_List'].value_counts()

print(tag_counts)
print("-" * 50)

khac_count = tag_counts.get('Khác', 0)
print(f"Remaining 'Khác' tags: {khac_count}")
