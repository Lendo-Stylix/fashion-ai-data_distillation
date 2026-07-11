import sys
import os
import re
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
    KEY_QUOTAS[key1] = 1190
if key2:
    KEY_QUOTAS[key2] = 575


MODEL_NAME = "models/gemma-4-26b-a4b-it"
ERROR_LOG_FILE = paths.DATA_PROCESSED / "translation_errors.json"
MAX_RETRIES = 20
MAX_WORKERS = 10

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
        print("--- API QUOTA STATUS ---")
        for k, q in self.key_quotas.items():
            print(f"Key ending with {k[-5:]}: {q} requests remaining")

key_manager = WeightedKeyManager(KEY_QUOTAS, rpm_limit=15)

ALLOWED_PATTERN = re.compile(
    r'^[\u0000-\u007F\u00C0-\u024F\u0300-\u036F\u1E00-\u1EFF\u2000-\u206F\u2010-\u2027\u2030-\u205E\u20A0-\u20CF\u2100-\u214F\s]+$'
)

def has_foreign_chars(text):
    for char in str(text):
        if not ALLOWED_PATTERN.match(char) and char.strip():
            return True
    return False

def check_translation_with_llm(en_input, en_output, vi_input, vi_output):
    user_prompt = (
        "Bạn là một Chuyên gia Ngôn ngữ học và Tư vấn thời trang. Kiểm tra xem bản dịch tiếng Việt có lỗi dịch thuật không.\n"
        "1. Lỗi giữ nguyên tiếng Anh không cần thiết.\n"
        "2. Lỗi sai nghĩa (Word-by-word).\n"
        "3. Lỗi xưng hô lộn xộn.\n\n"
        f"--- GỐC (EN) ---\nQ: {en_input}\nA: {en_output}\n\n"
        f"--- DỊCH (VI) ---\nQ: {vi_input}\nA: {vi_output}\n\n"
        "Chỉ trả về 'ERROR' hoặc 'OK':"
    )
    
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }
    headers = {"Content-Type": "application/json"}
    
    for attempt in range(MAX_RETRIES):
        key = key_manager.get_key_and_wait()
        if not key:
            print("❌ OUT OF QUOTA ACROSS ALL KEYS!")
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
                result = text.strip().upper()
                return 'ERROR' in result
            elif response.status_code == 429:
                time.sleep(10)
                continue
            else:
                # 500 or 503 error, wait and retry
                print(f"HTTP {response.status_code}. Retrying in 30s...")
                time.sleep(30)
                continue
        except Exception as e:
            print(f"Exception: {e}. Retrying in 30s...")
            time.sleep(30)
    
    return True # Fail-safe

def process_row(row):
    row_id = row['ID']
    if has_foreign_chars(row['translated_input']) or has_foreign_chars(row['translated_output']):
        return row_id, "L1"
    
    result = check_translation_with_llm(
        row['original_input'], row['original_output'], 
        row['translated_input'], row['translated_output']
    )
    if result == "QUOTA_EXCEEDED":
        return row_id, "QUOTA_EXCEEDED"
    elif result is True:
        return row_id, "L23"
    
    return row_id, "OK"

def main():
    print("Loading distilled dataset (1500 rows)...")
    df_eval = pd.read_csv(paths.DATA_PROCESSED / 'distilled_1500_pre_audit.csv')
    print(f"Total rows to audit: {len(df_eval)}")
    
    error_ids = []
    layer1_errors = 0
    layer23_errors = 0
    
    print("Starting REAL Translation Audit with Weighted Quota Manager...")
    key_manager.print_quota_status()
    
    processed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_row, row): row for _, row in df_eval.iterrows()}
            
        for future in as_completed(futures):
            row = futures[future]
            try:
                res_id, status = future.result()
                if status == "QUOTA_EXCEEDED":
                    print("Stopping execution due to quota.")
                    break
                elif status == "L1":
                    layer1_errors += 1
                    error_ids.append(res_id)
                elif status == "L23":
                    layer23_errors += 1
                    error_ids.append(res_id)
                
                processed_count += 1
                print(f"Processed {processed_count}/{len(df_eval)} rows. (L1: {layer1_errors}, L23: {layer23_errors})", flush=True)
            except Exception as e:
                print(f"Row {row['ID']} raised an exception: {e}", flush=True)

    print("\n--- AUDIT COMPLETE ---", flush=True)
    print(f"Total Rows Scanned: {processed_count}", flush=True)
    print(f"Layer 1 Errors (Foreign Chars): {layer1_errors}", flush=True)
    print(f"Layer 2/3 Errors (LLM Semantic/Fluency): {layer23_errors}", flush=True)
    print(f"Total Errors Found: {layer1_errors + layer23_errors}", flush=True)
    
    key_manager.print_quota_status()
    
    with open(ERROR_LOG_FILE, 'w') as f:
        json.dump({
            "error_ids": error_ids, 
            "layer1": layer1_errors, 
            "layer23": layer23_errors
        }, f)
    print(f"Saved to {ERROR_LOG_FILE}", flush=True)

if __name__ == "__main__":
    main()
