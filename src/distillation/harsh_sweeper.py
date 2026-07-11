import os
import re
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def has_ai_cliche(text):
    cliches = [
        r"(?i)xin chào", r"(?i)tôi là (một )?(trợ lý|ai|mô hình)", 
        r"(?i)dưới đây là", r"(?i)hy vọng điều này hữu ích",
        r"(?i)tóm lại,", r"(?i)nhìn chung,", r"(?i)tôi có thể giúp gì",
        r"(?i)như một trợ lý", r"(?i)như một chuyên gia",
        r"(?i)vui lòng cho tôi biết", r"(?i)xin lỗi, tôi không thể",
        r"(?i)tôi xin lỗi nhưng", r"(?i)lưu ý rằng,"
    ]
    for pattern in cliches:
        if re.search(pattern, str(text)):
            return True, f"AI Cliche Detected: {pattern}"
    return False, ""

def has_format_artifacts(text):
    text = str(text).strip()
    if text.startswith('"') and text.endswith('"'):
        return True, "Enclosed in quotes"
    if text.startswith('{') and text.endswith('}'):
        return True, "Enclosed in braces (JSON)"
    if re.search(r"\*\*[^*]+\*\*", text) and not re.search(r"\*\*[^*]+\*\*", text).group(0).lower().islower():
        # Markdown might be normal, but we flag suspicious excessive markdown
        pass
    if text.startswith("```"):
        return True, "Contains code block markdown"
    return False, ""

def has_localization_issues(text):
    text = str(text)
    # Check for URLs
    if re.search(r"(https?://\S+|www\.\S+)", text):
        return True, "Contains URL"
    # Check for foreign currency symbols ($ or £ or €)
    if re.search(r"[\$£€]", text):
        return True, "Contains foreign currency symbol"
    return False, ""

def has_repetition(q, a):
    q = str(q).strip().lower()
    a = str(a).strip().lower()
    if len(q) < 10: return False, ""
    
    # Check if answer starts with the question
    q_words = q.split()
    a_words = a.split()
    if len(q_words) > 5 and len(a_words) > 5:
        q_prefix = " ".join(q_words[:10])
        a_prefix = " ".join(a_words[:10])
        if q_prefix == a_prefix:
            return True, "Repetition of question in answer"
    return False, ""

def sweep():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    input_file = "../../data/isolated_proofs/distilled_final_guaranteed_clean.csv"
    passed_file = "../../data/isolated_proofs/ultimate_clean_1500.csv"
    failed_file = "../../data/isolated_proofs/harsh_failed_rows.csv"
    
    df = pd.read_csv(input_file)
    logging.info(f"Loaded {len(df)} rows for Harsh Sweeper.")
    
    passed_rows = []
    failed_rows = []
    
    for idx, row in df.iterrows():
        vi_q = row['translated_input']
        vi_a = row['translated_output']
        
        is_bad = False
        reasons = []
        
        # 1. AI Cliches
        bad_q, r_q = has_ai_cliche(vi_q)
        bad_a, r_a = has_ai_cliche(vi_a)
        if bad_q: reasons.append(r_q)
        if bad_a: reasons.append(r_a)
        
        # 2. Format Artifacts
        bad_fq, r_fq = has_format_artifacts(vi_q)
        bad_fa, r_fa = has_format_artifacts(vi_a)
        if bad_fq: reasons.append(r_fq)
        if bad_fa: reasons.append(r_fa)
        
        # 3. Localization
        bad_lq, r_lq = has_localization_issues(vi_q)
        bad_la, r_la = has_localization_issues(vi_a)
        if bad_lq: reasons.append(r_lq)
        if bad_la: reasons.append(r_la)
        
        # 4. Repetition
        bad_rep, r_rep = has_repetition(vi_q, vi_a)
        if bad_rep: reasons.append(r_rep)
        
        if reasons:
            row_copy = row.copy()
            row_copy['harsh_fail_reason'] = " | ".join(reasons)
            failed_rows.append(row_copy)
        else:
            passed_rows.append(row)
            
    # Save results
    if passed_rows:
        pd.DataFrame(passed_rows).to_csv(passed_file, index=False)
        
    if failed_rows:
        pd.DataFrame(failed_rows).to_csv(failed_file, index=False)
        
    logging.info(f"Sweep complete! Passed: {len(passed_rows)}, Failed: {len(failed_rows)}")

if __name__ == "__main__":
    sweep()
