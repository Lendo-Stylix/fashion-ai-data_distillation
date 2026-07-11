import os
import sys
import time
import json
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Import dependencies from run_batch_pipeline
from run_batch_pipeline import call_api_with_retry, key_manager, _CLIENTS, MODEL_TRANSLATE, MODEL_AUDIT, MAX_WORKERS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

NEEDS_RETRANS_FILE = "../../data/isolated_proofs/distilled_507_needs_retranslation.csv"
CLEAN_FILE = "../../data/isolated_proofs/distilled_final_guaranteed_clean.csv"

vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ'
                       'ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ')
ai_leaks = ['chuyên gia', 'dịch thuật', 'bắt buộc', 'perfect', 'needs_fix', 'critique', 'json', 'dịch xuất sắc']

def count_vi_chars(text):
    if not isinstance(text, str): return 0
    return sum(1 for c in text if c in vietnamese_chars)

def check_row_quality(en_q, en_a, vi_q, vi_a):
    vi_q = str(vi_q).strip()
    vi_a = str(vi_a).strip()
    en_q = str(en_q)
    en_a = str(en_a)
    
    # 1. Not Vietnamese
    if count_vi_chars(vi_q) == 0 or count_vi_chars(vi_a) == 0:
        return False, "Not_Vietnamese"
        
    # 2. Format QA
    if 'Q:' in vi_q or 'A:' in vi_a or 'Q:' in vi_a or 'A:' in vi_q or 'Question:' in vi_q or 'Answer:' in vi_a:
        return False, "Format_QA"
        
    # 3. Empty or short
    if not vi_q or not vi_a or len(vi_q) < 10 or len(vi_a) < 10:
        return False, "Empty_Or_Short"
        
    # 4. Length Anomaly
    if len(en_q) > 0 and len(vi_q) > 0:
        r_q = len(vi_q) / len(en_q)
        if r_q < 0.25 or r_q > 3.0:
            return False, "Length_Anomaly (Input)"
    if len(en_a) > 0 and len(vi_a) > 0:
        r_a = len(vi_a) / len(en_a)
        if r_a < 0.25 or r_a > 3.0:
            return False, "Length_Anomaly (Output)"
            
    # 5. AI Leakage
    vi_combined = (vi_q + ' ' + vi_a).lower()
    if any(w in vi_combined for w in ai_leaks):
        en_combined = (en_q + ' ' + en_a).lower()
        if 'perfect' in vi_combined and 'perfect' not in en_combined:
            return False, "AI_Leakage"
        elif any(w in vi_combined for w in ['dịch thuật', 'needs_fix', 'critique', 'bắt buộc']):
            return False, "AI_Leakage"
            
    return True, "OK"

def process_retranslate_batch(batch_df):
    trans_system = "Bạn là Chuyên gia Dịch thuật. Dịch sang tiếng Việt tự nhiên nhất. Đặc biệt chú ý khắc phục các LỖI BẢN DỊCH TRƯỚC (nếu có).\nBẮT BUỘC trả về JSON với cấu trúc: {\"translations\": [{\"id\": 1, \"new_vi_input\": \"...\", \"new_vi_output\": \"...\"}]}"
    
    trans_user = ""
    for _, row in batch_df.iterrows():
        rid = row['ID']
        trans_user += f"[ID {rid}]\n- Gốc (EN):\n  Q: {row['original_input']}\n  A: {row['original_output']}\n"
        reason = row.get('fail_reason', '')
        if pd.notna(reason) and reason:
            trans_user += f"- LỖI BẢN DỊCH TRƯỚC: {reason}\n"
        trans_user += "\n"
        
    trans_res = call_api_with_retry(MODEL_TRANSLATE, trans_system, trans_user, expected_key="translations")
    if not trans_res or 'translations' not in trans_res:
        return []
        
    translations = {item['id']: item for item in trans_res['translations']}
    
    # 2. Critique
    review_system = "Bạn là Chuyên gia Đánh giá Dịch thuật. Đánh giá bản dịch tiếng Việt so với bản gốc tiếng Anh. Phân loại status thành 'PERFECT' hoặc 'NEEDS_FIX'. Nếu 'NEEDS_FIX', giải thích lý do.\nBẮT BUỘC trả về JSON với cấu trúc: {\"reviews\": [{\"id\": 1, \"status\": \"PERFECT\" hoặc \"NEEDS_FIX\", \"critique\": \"lý do\"}]}"
    review_user = ""
    for _, row in batch_df.iterrows():
        rid = row['ID']
        if rid in translations:
            new_t = translations[rid]
            review_user += f"[ID {rid}]\n- Gốc (EN):\n  Q: {row['original_input']}\n  A: {row['original_output']}\n- Bản dịch mới (VI):\n  Q: {new_t.get('new_vi_input', '')}\n  A: {new_t.get('new_vi_output', '')}\n\n"
            
    review_res = call_api_with_retry(MODEL_AUDIT, review_system, review_user, expected_key="reviews")
    if not review_res or 'reviews' not in review_res:
        return list(translations.values())
        
    needs_fix_ids = [item['id'] for item in review_res['reviews'] if item['status'] == 'NEEDS_FIX']
    
    # 3. Refine
    if needs_fix_ids:
        refine_system = "Chuốt lại các bản dịch tiếng Việt dựa trên Critique để đạt điểm PERFECT.\nBẮT BUỘC trả về JSON với cấu trúc: {\"translations\": [{\"id\": 1, \"new_vi_input\": \"...\", \"new_vi_output\": \"...\"}]}"
        refine_user = ""
        review_critiques = {item['id']: item['critique'] for item in review_res['reviews']}
        for _, row in batch_df[batch_df['ID'].isin(needs_fix_ids)].iterrows():
            rid = row['ID']
            if rid in translations:
                new_t = translations[rid]
                refine_user += f"[ID {rid}]\n- Gốc (EN):\n  Q: {row['original_input']}\n  A: {row['original_output']}\n- Bản dịch nháp:\n  Q: {new_t.get('new_vi_input', '')}\n  A: {new_t.get('new_vi_output', '')}\n- Lỗi (Critique): {review_critiques.get(rid, '')}\n\n"
                
        refine_res = call_api_with_retry(MODEL_TRANSLATE, refine_system, refine_user, expected_key="translations")
        if refine_res and 'translations' in refine_res:
            for refined_item in refine_res['translations']:
                if refined_item['id'] in translations:
                    translations[refined_item['id']] = refined_item 
                    
    return list(translations.values())

def main():
    # Fix paths based on CWD being the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    max_loops = 10
    loop = 0
    
    while loop < max_loops:
        loop += 1
        try:
            df = pd.read_csv(NEEDS_RETRANS_FILE)
        except Exception as e:
            logging.error(f"Cannot read {NEEDS_RETRANS_FILE}: {e}")
            break
            
        if len(df) == 0:
            logging.info("All rows perfectly translated!")
            break
            
        logging.info(f"--- LOOP {loop}: Retranslating {len(df)} failed rows ---")
        
        batch_size = 10
        batches = [df.iloc[i:i + batch_size] for i in range(0, len(df), batch_size)]
        
        results_list = []
        logging.info(f"Processing {len(batches)} batches using ThreadPoolExecutor with {MAX_WORKERS} workers...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_batch = {executor.submit(process_retranslate_batch, b): b for b in batches}
            for future in as_completed(future_to_batch):
                try:
                    res = future.result()
                    results_list.extend(res)
                except Exception as e:
                    logging.error(f"Batch failed: {e}")
                
        good_rows = []
        bad_indices = []
        
        for idx, row in df.iterrows():
            rid = row['ID']
            matching_trans = next((x for x in results_list if x.get('id') == rid), None)
            
            if matching_trans:
                vi_q = matching_trans.get('new_vi_input', '')
                vi_a = matching_trans.get('new_vi_output', '')
                
                is_ok, reason = check_row_quality(row['original_input'], row['original_output'], vi_q, vi_a)
                if is_ok:
                    row_copy = row.copy()
                    row_copy['translated_input'] = vi_q
                    row_copy['translated_output'] = vi_a
                    good_rows.append(row_copy)
                else:
                    logging.warning(f"ID {rid} failed again: {reason}")
                    old_reason = str(row.get('fail_reason', ''))
                    if old_reason and old_reason != 'nan':
                        if reason not in old_reason:
                            df.at[idx, 'fail_reason'] = f"{old_reason} -> {reason}"
                        elif "VẪN BỊ LỖI" not in old_reason:
                            df.at[idx, 'fail_reason'] = f"{old_reason} (VẪN BỊ LỖI, HÃY ĐỌC KỸ LẠI YÊU CẦU!)"
                        else:
                            df.at[idx, 'fail_reason'] = old_reason
                    else:
                        df.at[idx, 'fail_reason'] = reason
                    bad_indices.append(idx)
            else:
                logging.warning(f"ID {rid} did not receive translation.")
                df.at[idx, 'fail_reason'] = "API did not return translation"
                bad_indices.append(idx)
                
        # Append good rows to clean file
        if good_rows:
            good_df = pd.DataFrame(good_rows)
            clean_df = pd.read_csv(CLEAN_FILE)
            clean_df = pd.concat([clean_df, good_df], ignore_index=True)
            clean_df = clean_df.drop_duplicates(subset=['translated_input'], keep='first')
            clean_df.to_csv(CLEAN_FILE, index=False)
            logging.info(f"Appended {len(good_rows)} good rows. Clean file now has {len(clean_df)} rows.")
            
        # Update needs retrans file
        if bad_indices:
            bad_df = df.loc[bad_indices]
            bad_df.to_csv(NEEDS_RETRANS_FILE, index=False)
            logging.info(f"{len(bad_df)} rows still bad.")
        else:
            # Clear file
            pd.DataFrame(columns=df.columns).to_csv(NEEDS_RETRANS_FILE, index=False)
            logging.info("Zero bad rows left!")
            break
            
if __name__ == "__main__":
    main()
