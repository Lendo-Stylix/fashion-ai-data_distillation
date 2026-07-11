import os
import sys
import json
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from typing import List, Literal
from openai import OpenAI
from dotenv import load_dotenv
import queue
import threading

# Setup logging
log_file = "pipeline_run.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
sys.stdout.reconfigure(encoding='utf-8')

# Config
load_dotenv()

# Extract keys
API_KEYS = []
for i in range(1, 10):
    key = os.environ.get(f"DASHSCOPE_API_KEY_{i}")
    if key:
        API_KEYS.append(key)

if not API_KEYS:
    # Fallback to check GEMMA_API_KEY if testing, but ideally should be DASHSCOPE_API_KEY
    key = os.environ.get("DASHSCOPE_API_KEY")
    if key:
        API_KEYS.append(key)

class KeyManager:
    def __init__(self, keys, max_concurrent_per_key=2, min_delay_between_requests=1.0):
        self.queue = queue.Queue()
        self.last_used = {key: 0.0 for key in keys}
        self.lock = threading.Lock()
        self.min_delay = min_delay_between_requests
        for key in keys:
            for _ in range(max_concurrent_per_key):
                self.queue.put(key)
                
    def acquire(self):
        key = self.queue.get()
        with self.lock:
            now = time.time()
            ready_time = max(now, self.last_used.get(key, 0.0) + self.min_delay)
            self.last_used[key] = ready_time
        
        sleep_time = ready_time - now
        if sleep_time > 0:
            time.sleep(sleep_time)
        return key

    def release(self, key):
        self.queue.put(key)

key_manager = KeyManager(API_KEYS, max_concurrent_per_key=10, min_delay_between_requests=0.2)
base_url = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
_CLIENTS = {k: OpenAI(api_key=k, base_url=base_url, timeout=300) for k in API_KEYS}

MODEL_AUDIT = "deepseek-v4-flash"
MODEL_TRANSLATE = "deepseek-v4-flash"
BATCH_SIZE = 10  # DeepSeek is fast and stable, we can increase batch size safely
MAX_WORKERS = len(API_KEYS) * 10

# Output Directories
ISOLATED_DIR = "data/isolated_proofs"
os.makedirs(ISOLATED_DIR, exist_ok=True)
ERRORS_FILE = os.path.join(ISOLATED_DIR, "translation_errors.json")
OUTPUT_CSV = os.path.join(ISOLATED_DIR, "distilled_1500_retranslated.csv")

# ================= HELPER FUNCTIONS =================
# Global fallback chain
FALLBACK_CHAIN = ['qwen-flash', 'qwen-plus', 'qwen-turbo', 'qwen-flash-2025-07-28', 'qwen-plus-2025-09-11', 'qwen-plus-2025-07-14', 'qwen-plus-latest']
CURRENT_MODEL_INDEX = 0

def call_api_with_retry(model_name, system_instruction, user_data, expected_key, max_attempts=8):
    global CURRENT_MODEL_INDEX
    for attempt in range(max_attempts):
        api_key = key_manager.acquire()
        client = _CLIENTS[api_key]
        current_model = FALLBACK_CHAIN[CURRENT_MODEL_INDEX]
        
        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_data}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw_json = response.choices[0].message.content
            key_manager.release(api_key)
            
            # Clean markdown code blocks if present
            cleaned_json = raw_json.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            elif cleaned_json.startswith("```"):
                cleaned_json = cleaned_json[3:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]
            cleaned_json = cleaned_json.strip()
            
            parsed = json.loads(cleaned_json)
            if expected_key and expected_key not in parsed:
                raise ValueError(f"Missing expected key '{expected_key}' in response")
            return parsed
            
        except json.JSONDecodeError as e:
            key_manager.release(api_key)
            logging.warning(f"JSONDecodeError on attempt {attempt+1}: {e}. Raw snippet: {raw_json[:50]}... Retrying...")
            time.sleep(5)
        except ValueError as ve:
            key_manager.release(api_key)
            logging.warning(f"Validation Error on attempt {attempt+1}: {ve}. Retrying...")
            time.sleep(5)
        except Exception as e:
            key_manager.release(api_key)
            error_msg = str(e).lower()
            if "403" in error_msg or "quota" in error_msg or "insufficient" in error_msg:
                if CURRENT_MODEL_INDEX < len(FALLBACK_CHAIN) - 1:
                    CURRENT_MODEL_INDEX += 1
                    new_model = FALLBACK_CHAIN[CURRENT_MODEL_INDEX]
                    logging.error(f"QUOTA EXHAUSTED for {current_model}. Falling back to {new_model}...")
                    backoff_time = 2
                else:
                    logging.error(f"QUOTA EXHAUSTED for all fallback models. Stopping.")
                    raise e
            elif "429" in error_msg or "rate limit" in error_msg:
                logging.error(f"Rate limit exceeded for key ...{api_key[-4:]}. Cooldown 30s.")
                with key_manager.lock:
                    key_manager.last_used[api_key] = max(key_manager.last_used.get(api_key, 0.0), time.time() + 30)
                backoff_time = 2 
            else:
                backoff_time = 15 * (2 ** attempt) 
            logging.error(f"API Error on attempt {attempt+1} with key ...{api_key[-4:]} for model {current_model}: {e}. Sleeping {backoff_time}s...")
            time.sleep(backoff_time)
    return None

def process_audit_batch(batch_df):
    system_instruction = "Bạn là Chuyên gia Đánh giá Dịch thuật Thời trang. Hãy tìm ra các lỗi dịch thuật (sai nghĩa, sượng, word-by-word) trong các bản dịch tiếng Việt sau so với bản gốc tiếng Anh. Trả về is_error=true nếu có lỗi, ngược lại false. Giải thích lý do (critique).\n\nBẮT BUỘC trả về JSON với cấu trúc: {\"results\": [{\"id\": 1, \"is_error\": true/false, \"critique\": \"lý do\"}]}"
    
    user_data = ""
    for _, row in batch_df.iterrows():
        user_data += f"[ID {row['ID']}]\n- Gốc (EN):\n  Q: {row['original_input']}\n  A: {row['original_output']}\n- Dịch (VI):\n  Q: {row['translated_input']}\n  A: {row['translated_output']}\n\n"
    
    res = call_api_with_retry(MODEL_AUDIT, system_instruction, user_data, expected_key="results")
    if res and 'results' in res:
        return res['results']
    return []

def process_retranslate_batch(batch_df, critiques_dict):
    # Pass 1: Retranslate
    trans_system = "Bạn là Chuyên gia Dịch thuật Thời trang. Hãy dịch lại các câu tiếng Anh sau sang tiếng Việt tự nhiên nhất. Các câu này trước đây dịch bị lỗi, tôi có kèm theo Nhận xét Lỗi (Critique). Hãy sửa triệt để các lỗi đó.\n\nBẮT BUỘC trả về JSON với cấu trúc: {\"translations\": [{\"id\": 1, \"new_vi_input\": \"...\", \"new_vi_output\": \"...\"}]}"
    
    trans_user = ""
    for _, row in batch_df.iterrows():
        rid = row['ID']
        trans_user += f"[ID {rid}]\n- Gốc (EN):\n  Q: {row['original_input']}\n  A: {row['original_output']}\n- Lỗi cần sửa (Critique): {critiques_dict.get(rid, '')}\n\n"
        
    trans_res = call_api_with_retry(MODEL_TRANSLATE, trans_system, trans_user, expected_key="translations")
    if not trans_res or 'translations' not in trans_res:
        return []
        
    translations = {item['id']: item for item in trans_res['translations']}
    
    # Pass 2: Critique New
    review_system = "Bạn là Chuyên gia Đánh giá Dịch thuật. Hãy xem xét các bản dịch tiếng Việt mới này so với bản gốc tiếng Anh. Phân loại status thành 'PERFECT' hoặc 'NEEDS_FIX'. Nếu 'NEEDS_FIX', giải thích lý do.\n\nBẮT BUỘC trả về JSON với cấu trúc: {\"reviews\": [{\"id\": 1, \"status\": \"PERFECT\" hoặc \"NEEDS_FIX\", \"critique\": \"lý do\"}]}"
    
    review_user = ""
    for _, row in batch_df.iterrows():
        rid = row['ID']
        if rid in translations:
            new_t = translations[rid]
            review_user += f"[ID {rid}]\n- Gốc (EN):\n  Q: {row['original_input']}\n  A: {row['original_output']}\n- Bản dịch mới (VI):\n  Q: {new_t['new_vi_input']}\n  A: {new_t['new_vi_output']}\n\n"
            
    review_res = call_api_with_retry(MODEL_AUDIT, review_system, review_user, expected_key="reviews")
    if not review_res or 'reviews' not in review_res:
        return list(translations.values())
        
    needs_fix_ids = [item['id'] for item in review_res['reviews'] if item['status'] == 'NEEDS_FIX']
    
    # Pass 3: Refine
    if needs_fix_ids:
        refine_system = "Hãy chuốt lại các bản dịch tiếng Việt sau dựa trên Nhận xét lỗi (Critique) để đạt điểm PERFECT.\n\nBẮT BUỘC trả về JSON với cấu trúc: {\"translations\": [{\"id\": 1, \"new_vi_input\": \"...\", \"new_vi_output\": \"...\"}]}"
        
        refine_user = ""
        review_critiques = {item['id']: item['critique'] for item in review_res['reviews']}
        for _, row in batch_df[batch_df['ID'].isin(needs_fix_ids)].iterrows():
            rid = row['ID']
            if rid in translations:
                new_t = translations[rid]
                refine_user += f"[ID {rid}]\n- Gốc (EN):\n  Q: {row['original_input']}\n  A: {row['original_output']}\n- Bản dịch nháp:\n  Q: {new_t['new_vi_input']}\n  A: {new_t['new_vi_output']}\n- Cần sửa (Critique): {review_critiques.get(rid, '')}\n\n"
                
        refine_res = call_api_with_retry(MODEL_TRANSLATE, refine_system, refine_user, expected_key="translations")
        if refine_res and 'translations' in refine_res:
            for refined_item in refine_res['translations']:
                if refined_item['id'] in translations:
                    translations[refined_item['id']] = refined_item 

    return list(translations.values())

def main():
    logging.info("=== STARTING BATCH PIPELINE (DEEPSEEK / DASHSCOPE) ===")
    if not API_KEYS:
        logging.error("No DASHSCOPE_API_KEY found! Exiting.")
        sys.exit(1)
        
    logging.info(f"Initialized KeyManager with {len(API_KEYS)} keys. Total MAX_WORKERS = {MAX_WORKERS}")
    df = pd.read_csv('data/processed/distilled_1500_pre_audit.csv')
    total_rows = len(df)
    
    # ------------------ STEP 3 ------------------
    logging.info(f"--- STEP 3: AUDITING {total_rows} ROWS ---")
    
    all_audit_results = {}
    if os.path.exists(ERRORS_FILE):
        try:
            with open(ERRORS_FILE, 'r', encoding='utf-8') as f:
                all_audit_results = json.load(f)
            logging.info(f"Loaded {len(all_audit_results)} existing audit results.")
        except Exception as e:
            logging.error(f"Could not load existing errors: {e}")

    rows_to_audit = df[~df['ID'].astype(str).isin(all_audit_results.keys())]
    
    if len(rows_to_audit) > 0:
        batches = [rows_to_audit.iloc[i:i + BATCH_SIZE] for i in range(0, len(rows_to_audit), BATCH_SIZE)]
        logging.info(f"Creating {len(batches)} batches for Step 3...")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_batch = {executor.submit(process_audit_batch, batch): batch for batch in batches}
            
            for future in as_completed(future_to_batch):
                results = future.result()
                for res in results:
                    all_audit_results[str(res['id'])] = {
                        "is_error": res['is_error'],
                        "critique": res['critique']
                    }
                with open(ERRORS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_audit_results, f, ensure_ascii=False, indent=2)
                logging.info(f"Progress Step 3: {len(all_audit_results)}/{total_rows} rows audited.")
                
    logging.info("STEP 3 COMPLETED.")

    # ------------------ STEP 4 ------------------
    error_ids = [int(i) for i, data in all_audit_results.items() if data['is_error']]
    logging.info(f"--- STEP 4: RETRANSLATING {len(error_ids)} ERROR ROWS ---")
    
    df_retranslated = df.copy()
    
    STEP4_CHECKPOINT = os.path.join(ISOLATED_DIR, "step4_translations.json")
    all_translations = {}
    if os.path.exists(STEP4_CHECKPOINT):
        try:
            with open(STEP4_CHECKPOINT, 'r', encoding='utf-8') as f:
                all_translations = json.load(f)
            logging.info(f"Loaded {len(all_translations)} existing translations.")
        except:
            pass
            
    rows_to_translate = df[df['ID'].isin(error_ids) & ~df['ID'].astype(str).isin(all_translations.keys())]
    
    if len(rows_to_translate) > 0:
        batches = [rows_to_translate.iloc[i:i + BATCH_SIZE] for i in range(0, len(rows_to_translate), BATCH_SIZE)]
        logging.info(f"Creating {len(batches)} batches for Step 4...")
        
        critiques_dict = {int(i): data['critique'] for i, data in all_audit_results.items()}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_batch = {executor.submit(process_retranslate_batch, batch, critiques_dict): batch for batch in batches}
            
            for future in as_completed(future_to_batch):
                results = future.result()
                for res in results:
                    all_translations[str(res['id'])] = {
                        "new_vi_input": res['new_vi_input'],
                        "new_vi_output": res['new_vi_output']
                    }
                with open(STEP4_CHECKPOINT, 'w', encoding='utf-8') as f:
                    json.dump(all_translations, f, ensure_ascii=False, indent=2)
                logging.info(f"Progress Step 4: {len(all_translations)}/{len(error_ids)} rows translated.")
                
    logging.info("STEP 4 COMPLETED. Applying translations to CSV...")
    
    for i_str, trans_data in all_translations.items():
        idx = df_retranslated.index[df_retranslated['ID'] == int(i_str)].tolist()
        if idx:
            df_retranslated.at[idx[0], 'translated_input'] = trans_data['new_vi_input']
            df_retranslated.at[idx[0], 'translated_output'] = trans_data['new_vi_output']
            
    df_retranslated.to_csv(OUTPUT_CSV, index=False)
    logging.info(f"Pipeline successfully generated: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
