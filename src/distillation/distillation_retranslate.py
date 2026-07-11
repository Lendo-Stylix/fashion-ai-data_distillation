import sys
import os
import json
import time
import requests
import pandas as pd
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from configs import paths

from dotenv import load_dotenv
load_dotenv()

key1 = os.getenv("GEMMA_API_KEY_1", "")
key2 = os.getenv("GEMMA_API_KEY_2", "")

KEY_QUOTAS = {}
if key1:
    KEY_QUOTAS[key1] = 146
if key2:
    KEY_QUOTAS[key2] = 0


MODEL_NAME = "models/gemma-4-26b-a4b-it"
ERROR_LOG_FILE = paths.DATA_PROCESSED / "translation_errors.json"
INPUT_CSV = paths.DATA_PROCESSED / "distilled_1500_pre_audit.csv"
OUTPUT_CSV = paths.DATA_PROCESSED / "distilled_1500_post_audit.csv"
MAX_RETRIES = 20
MAX_WORKERS = 5

class WeightedKeyManager:
    def __init__(self, key_quotas, rpm_limit=15):
        self.key_quotas = dict(key_quotas)
        self.last_used = {k: 0.0 for k in key_quotas.keys()}
        self.lock = threading.Lock()
        self.min_interval = 60.0 / rpm_limit + 0.1 

    def get_key_and_wait(self):
        while True:
            with self.lock:
                available_keys = [k for k, q in self.key_quotas.items() if q > 0]
                if not available_keys:
                    return None 
                
                available_keys.sort(key=lambda k: self.key_quotas[k], reverse=True)
                
                now = time.time()
                for k in available_keys:
                    if now - self.last_used[k] >= self.min_interval:
                        self.last_used[k] = now
                        self.key_quotas[k] -= 1
                        return k
            time.sleep(0.5)

    def print_quota_status(self):
        print("--- API QUOTA STATUS ---", flush=True)
        for k, q in self.key_quotas.items():
            print(f"Key ending with {k[-5:]}: {q} requests remaining", flush=True)

key_manager = WeightedKeyManager(KEY_QUOTAS, rpm_limit=15)

def retranslate_text(en_text):
    user_prompt = (
        "Bạn là một Chuyên gia Dịch thuật. Dịch đoạn văn bản tiếng Anh sau sang tiếng Việt tự nhiên, chính xác, và phù hợp với bối cảnh tư vấn thời trang.\n"
        "Đảm bảo không dịch 'word-by-word', sử dụng đúng thuật ngữ chuyên ngành thời trang (ví dụ: 'rise' là cạp quần, 'stitching' là đường may).\n\n"
        f"--- GỐC (EN) ---\n{en_text}\n\n"
        "Chỉ trả về bản dịch tiếng Việt, không giải thích gì thêm:"
    )
    
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }
    headers = {"Content-Type": "application/json"}
    
    for attempt in range(MAX_RETRIES):
        key = key_manager.get_key_and_wait()
        if not key:
            return "QUOTA_EXCEEDED"

        url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={key}"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                parts = response.json()['candidates'][0]['content']['parts']
                text = ""
                for p in parts:
                    if not p.get('thought', False):
                        text += p.get('text', '')
                return text.strip()
            elif response.status_code == 429:
                time.sleep(10)
                continue
            else:
                # 500 or 503 error, wait and retry
                time.sleep(30)
                continue
        except Exception as e:
            time.sleep(30)
    
    return "ERROR_TIMEOUT"

def process_row(row):
    row_id = row['ID']
    new_vi_input = retranslate_text(row['original_input'])
    if new_vi_input == "QUOTA_EXCEEDED":
        return row_id, "QUOTA_EXCEEDED", None, None
        
    new_vi_output = retranslate_text(row['original_output'])
    if new_vi_output == "QUOTA_EXCEEDED":
        return row_id, "QUOTA_EXCEEDED", None, None
        
    return row_id, "SUCCESS", new_vi_input, new_vi_output

def main():
    if not ERROR_LOG_FILE.exists():
        print(f"Error file {ERROR_LOG_FILE} not found!")
        return
        
    with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
        errors = json.load(f)
        
    error_ids = set(errors.get('error_ids', []))
    print(f"Loaded {len(error_ids)} error IDs to retranslate.")
    
    # Load dataset. If output exists, we resume from output.
    if OUTPUT_CSV.exists():
        df = pd.read_csv(OUTPUT_CSV)
        print("Loaded existing post-audit dataset to resume.")
    else:
        df = pd.read_csv(INPUT_CSV)
        df['audit_status'] = 'PENDING'
        print("Loaded pre-audit dataset.")
    
    # Identify which error IDs still need retranslation
    pending_ids = df[(df['ID'].isin(error_ids)) & (df['audit_status'] != 'RETRANSLATED')]['ID'].tolist()
    print(f"Total rows remaining to retranslate: {len(pending_ids)}")
    
    if len(pending_ids) == 0:
        print("No rows need retranslation. DONE!")
        return

    df_pending = df[df['ID'].isin(pending_ids)]
    
    print("Starting Re-translation with Weighted Quota Manager...", flush=True)
    key_manager.print_quota_status()
    
    processed_count = 0
    quota_exhausted = False
    
    # Process
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_row, row): row for _, row in df_pending.iterrows()}
            
        for future in as_completed(futures):
            row = futures[future]
            try:
                res_id, status, new_input, new_output = future.result()
                if status == "QUOTA_EXCEEDED":
                    quota_exhausted = True
                    break
                elif status == "SUCCESS" and new_input and new_output and new_input != "ERROR_TIMEOUT" and new_output != "ERROR_TIMEOUT":
                    # Update dataframe
                    df.loc[df['ID'] == res_id, 'translated_input'] = new_input
                    df.loc[df['ID'] == res_id, 'translated_output'] = new_output
                    df.loc[df['ID'] == res_id, 'audit_status'] = 'RETRANSLATED'
                    processed_count += 1
                    print(f"Retranslated {processed_count}/{len(pending_ids)} rows.", flush=True)
                else:
                    print(f"Row {res_id} failed to translate (timeout).", flush=True)
                    
            except Exception as e:
                print(f"Row {row['ID']} raised an exception: {e}", flush=True)
            
            # Save every 5 rows to prevent data loss
            if processed_count % 5 == 0:
                df.to_csv(OUTPUT_CSV, index=False)

    df.to_csv(OUTPUT_CSV, index=False)
    print("\n--- RETRANSLATION RUN COMPLETE ---", flush=True)
    print(f"Rows Successfully Retranslated this run: {processed_count}", flush=True)
    key_manager.print_quota_status()
    
    if quota_exhausted:
        print("\n❌ QUOTA EXHAUSTED! Please wait for quota reset or add more keys.", flush=True)
    else:
        print("\n✅ All rows have been retranslated!", flush=True)

if __name__ == "__main__":
    main()
