import pandas as pd
import re
import os

def clean_qa_prefixes():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    file_path = '../../data/isolated_proofs/distilled_1488_perfect.csv'
    df = pd.read_csv(file_path)
    
    prefixes_to_strip = [
        r"^hỏi:\s*",
        r"^đáp:\s*",
        r"^câu hỏi:\s*",
        r"^trả lời:\s*",
        r"^q:\s*",
        r"^a:\s*",
        r"^question:\s*",
        r"^answer:\s*"
    ]
    
    pattern = "(?i)" + "|".join(prefixes_to_strip)
    
    affected_rows = 0
    for idx, row in df.iterrows():
        changed = False
        t_in = str(row['translated_input']).strip()
        t_out = str(row['translated_output']).strip()
        
        new_t_in = re.sub(pattern, "", t_in).strip()
        if new_t_in != t_in:
            df.at[idx, 'translated_input'] = new_t_in
            changed = True
            
        new_t_out = re.sub(pattern, "", t_out).strip()
        if new_t_out != t_out:
            df.at[idx, 'translated_output'] = new_t_out
            changed = True
            
        if changed:
            affected_rows += 1
            
    df.to_csv(file_path, index=False)
    print(f"Removed Q&A prefixes from {affected_rows} rows.")

if __name__ == "__main__":
    clean_qa_prefixes()
