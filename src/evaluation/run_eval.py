import csv
import json
import requests
import time
import re
import os
import argparse
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from configs import paths


# --- CONFIGURATION ---
load_dotenv()
API_KEYS = []
if os.getenv("GEMMA_API_KEY_1"): API_KEYS.append(os.getenv("GEMMA_API_KEY_1"))
if os.getenv("GEMMA_API_KEY_2"): API_KEYS.append(os.getenv("GEMMA_API_KEY_2"))
if os.getenv("GEMMA_API_KEY_3"): API_KEYS.append(os.getenv("GEMMA_API_KEY_3"))

if not API_KEYS:
    raise ValueError("No API Keys found in .env file!")

MAX_RETRIES = 5 # max retries per batch
MODEL_NAME = "models/gemma-4-31b-it"
RUBRIC_FILE = paths.RUBRIC_FILE
DATASET_FILE = paths.CLEANED_10K_CSV
OUTPUT_FILE = paths.EVALUATED_CSV
FAILED_FILE = paths.FAILED_BATCHES_JSON

BATCH_SIZE = 5
VALID_CATEGORIES = ['Dáng người', 'Hoàn cảnh', 'Kiến thức cơ bản', 'Phong cách', 'Khác', 'Làm đẹp & Chăm sóc cá nhân', 'Phong thái & Tâm lý', 'Mua sắm & Quản lý tủ đồ', 'Bảo quản & Thời trang bền vững', 'Phong cách sống']
MAX_WORKERS = len(API_KEYS) * 4  # 4 luồng cho mỗi key là rất an toàn, đảm bảo chạy song song

# Locks for Thread Safety
csv_lock = threading.Lock()
failed_lock = threading.Lock()
global_failed_batches = []

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(paths.EVAL_LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- KEY MANAGER TỐI ƯU RPM ---
class KeyManager:
    def __init__(self, keys, rpm_limit=15):
        self.keys = keys
        self.last_used = {k: 0.0 for k in keys}
        self.lock = threading.Lock()
        # Để đảm bảo không bao giờ vượt 15 RPM, mỗi key phải cách nhau ít nhất (60 / 15) giây = 4 giây.
        # Ta đặt 4.1s cho an toàn tuyệt đối.
        self.min_interval = 60.0 / rpm_limit + 0.1 

    def get_key_and_wait(self):
        """Lấy một key khả dụng. Nếu chưa có, sẽ block đợi."""
        while True:
            with self.lock:
                now = time.time()
                for k in self.keys:
                    if now - self.last_used[k] >= self.min_interval:
                        self.last_used[k] = now
                        # Trả về key ẩn đi một nửa để log an toàn
                        return k
            time.sleep(0.5)

key_manager = KeyManager(API_KEYS, rpm_limit=15)

def read_rubric():
    with open(RUBRIC_FILE, 'r', encoding='utf-8') as f:
        return f.read()

def get_data(limit=None, target_ids=None):
    data = []
    with open(DATASET_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for i, row in enumerate(reader):
            row_id = i + 1
            if target_ids and row_id not in target_ids:
                continue
            if limit and len(data) >= limit:
                break
            data.append({
                "id": row_id,
                "input": row[2],
                "output": row[3]
            })
    return data

def call_gemma_with_retry(system_instruction, batch_data):
    user_prompt = "Hãy đánh giá các câu sau theo Rubric. CHỈ TRẢ VỀ KẾT QUẢ ĐÚNG ĐỊNH DẠNG YÊU CẦU, KHÔNG GIẢI THÍCH GÌ THÊM.\n\n"
    for item in batch_data:
        user_prompt += f"--- Câu ID: {item['id']} ---\n"
        user_prompt += f"Ngữ cảnh (Hỏi): {item['input']}\n"
        user_prompt += f"Câu trả lời (Đáp): {item['output']}\n\n"
    
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }
    headers = {"Content-Type": "application/json"}
    
    base_sleep = 5
    for attempt in range(MAX_RETRIES):
        # Lấy key và đảm bảo thỏa mãn RPM limit
        key = key_manager.get_key_and_wait()
        url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={key}"
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=180)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text'], None
            elif response.status_code == 429:
                sleep_duration = base_sleep * (2 ** attempt)
                logging.warning(f"Bị Rate Limit (429). Exponential backoff: sleep {sleep_duration}s...")
                time.sleep(sleep_duration)
                continue
            else:
                sleep_duration = base_sleep * (2 ** attempt)
                logging.warning(f"API Error {response.status_code}: {response.text}. Retrying in {sleep_duration}s...")
                time.sleep(sleep_duration)
                continue
        except requests.exceptions.RequestException as e:
            sleep_duration = base_sleep * (2 ** attempt)
            logging.error(f"Lỗi kết nối mạng: {e}. Retrying in {sleep_duration}s...")
            time.sleep(sleep_duration)
            
    return None, f"Thất bại sau {MAX_RETRIES} lần thử nghiệm."

def validate_and_extract(result_text, expected_ids):
    parsed_results = {}
    lines = result_text.split('\n')
    for line in lines:
        line = line.strip()
        line = line.replace('*', '').replace('`', '')
        
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 5:
            try:
                row_id = int(re.sub(r'\D', '', parts[0]))
                if row_id not in expected_ids:
                    continue
                detail = int(re.sub(r'\D', '', parts[1]))
                difficulty = int(re.sub(r'\D', '', parts[2]))
                vocab = int(re.sub(r'\D', '', parts[3]))
                tags_str = parts[4]
                
                # Check logic IF-ELSE
                if not (1 <= detail <= 3 and 1 <= difficulty <= 3 and 1 <= vocab <= 3):
                    continue
                
                # Check NLP Category
                extracted_tags = []
                for valid_cat in VALID_CATEGORIES:
                    if valid_cat.lower() in tags_str.lower():
                        extracted_tags.append(valid_cat)
                
                if not extracted_tags:
                    continue 
                
                parsed_results[row_id] = {
                    'detail': detail,
                    'difficulty': difficulty,
                    'vocab': vocab,
                    'tags': ', '.join(extracted_tags)
                }
            except (ValueError, IndexError):
                continue
                
    missing = [i for i in expected_ids if i not in parsed_results]
    return parsed_results, missing

def load_failed_batches():
    if not os.path.exists(FAILED_FILE):
        return []
    with open(FAILED_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_failed_batches(failed_list):
    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        json.dump(failed_list, f)

def get_fallback_target_ids(failed_list):
    target_ids = set()
    for item in failed_list:
        if isinstance(item, list):
            for i in item:
                target_ids.add(i)
        else:
            target_ids.add(item)
    return target_ids

def process_batch(batch, rubric, processed_ids):
    batch_ids = [x['id'] for x in batch]
    if all(bid in processed_ids for bid in batch_ids):
        return
        
    logging.info(f"--- Đang xử lý Batch (IDs: {batch_ids}) ---")
    result_text, error = call_gemma_with_retry(rubric, batch)
    
    if error:
        logging.error(f"❌ THẤT BẠI (Batch Error): {error}")
        with failed_lock:
            global_failed_batches.append(batch_ids)
            save_failed_batches(global_failed_batches)
    else:
        parsed_data, missing_ids = validate_and_extract(result_text, batch_ids)
        
        if parsed_data:
            with csv_lock:
                with open(OUTPUT_FILE, 'a', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    for row_id, data in parsed_data.items():
                        writer.writerow([row_id, data['detail'], data['difficulty'], data['vocab'], data['tags']])
            logging.info(f"✅ Đã trích xuất và lưu {len(parsed_data)} kết quả hợp lệ.")
            
        if missing_ids:
            logging.warning(f"⚠️ CẢNH BÁO: Thiếu hoặc sai format cho ID: {missing_ids}. Đã track vào fallback.")
            with failed_lock:
                global_failed_batches.append(missing_ids)
                save_failed_batches(global_failed_batches)

def main():
    global global_failed_batches
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='Chỉ test 10 dòng đầu')
    parser.add_argument('--fallback', action='store_true', help='Chỉ chạy lại các ID bị lỗi trong failed_batches.json')
    args = parser.parse_args()

    rubric = read_rubric()
    
    target_ids = None
    if args.fallback:
        failed_list = load_failed_batches()
        if not failed_list:
            logging.info("Không có batch nào bị lỗi để chạy fallback.")
            return
        target_ids = get_fallback_target_ids(failed_list)
        logging.info(f"Đã nạp {len(target_ids)} ID cần fallback.")
        save_failed_batches([])
        global_failed_batches = []
    else:
        global_failed_batches = load_failed_batches()

    limit = 10 if args.test else None
    items = get_data(limit=limit, target_ids=target_ids)
    
    if not items:
        logging.info("Không có dữ liệu để xử lý.")
        return

    processed_ids = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row:
                    processed_ids.add(int(row[0]))
    else:
        with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Detail', 'Difficulty', 'Vocab', 'Tags'])
            
    logging.info(f"Bắt đầu xử lý với {len(API_KEYS)} API Keys sử dụng Đa luồng (Max Workers: {MAX_WORKERS})...")
    
    batches = [items[i:i+BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_batch, batch, rubric, processed_ids) for batch in batches]
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Lỗi không xác định trong luồng: {e}")
            
    logging.info("[HOÀN THÀNH] Tiến trình đa luồng đã hoàn tất.")

if __name__ == "__main__":
    main()
