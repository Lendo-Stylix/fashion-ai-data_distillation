# -* - coding: utf-8 -*-
"""
run_reasoning_pipeline.py — Giai đoạn 5: Tự động chạy toàn bộ quy trình chưng cất dữ liệu sinh Reasoning & Cross-Check cho 1488 dòng
===========================================================================================================
Cơ chế:
  - Chạy Đa luồng (Multi-threading): Hỗ trợ chạy đồng thời tối đa N luồng (N_WORKERS) qua ThreadPoolExecutor.
  - Sử dụng khóa đồng bộ (Lock) khi cập nhật index mô hình của Router và ghi file checkpoint.
  - Checkpoint: Lưu lũy tiến vào file JSON và CSV để có thể resume nếu bị ngắt quãng giữa chừng.
  - Tuân thủ config/paths.py tuyệt đối.
"""

import json
import os
import sys
import time
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Đảm bảo có thể import configs
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from configs.paths import STRATIFIED_CSV, DATA_REASONING, DATA_FINAL

load_dotenv(ROOT / ".env")

API_KEY = os.getenv("DASHSCOPE_API_KEY_1")
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

GEN_MODELS = [
    "qwen3.7-max",
    "qwen3.7-max-2026-06-08",
    "qwen3.7-max-2026-05-20",
    "qwen3.7-max-2026-05-17",
    "qwen3.7-max-preview",
    "qwen3.7-plus",
    "qwen3.7-plus-2026-05-26"
]

JUDGE_MODELS = [
    "qwen3.6-max-preview",
    "qwen3.6-plus",
    "qwen3.5-plus",
    "qwen3.5-plus-2026-04-20",
    "qwen3.5-plus-2026-02-15",
    "qwen3.6-27b",
    "qwen3.5-27b",
    "qwen3.6-flash",
    "qwen3.6-flash-2026-04-16",
    "qwen3.5-flash",
    "qwen3.5-flash-2026-02-23"
]

# Chỉ mục mô hình hiện tại (sẽ lưu trạng thái)
current_gen_idx = 0
current_judge_idx = 0

# Khóa đồng bộ luồng
index_lock = threading.Lock()
checkpoint_lock = threading.Lock()

OUTPUT_LOG = DATA_REASONING / "reasoning_generation_log.json"
FINAL_OUTPUT_CSV = DATA_FINAL / "final_distilled_reasoning_1488.csv"

# Cấu hình đa luồng
N_WORKERS = 16

if not API_KEY:
    print("[FATAL] Không tìm thấy DASHSCOPE_API_KEY_1 trong .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# --------------------------------------------------------------------------- #
#  Prompt Templates
# --------------------------------------------------------------------------- #
REASONING_SYSTEM = """Bạn là chuyên gia tư vấn thời trang hàng đầu Việt Nam với hơn 15 năm kinh nghiệm.
Khi nhận câu hỏi về thời trang, hãy thực hiện theo hai bước:
1. Suy luận kỹ lưỡng trong thẻ <think>: Phân tích câu hỏi, vận dụng kiến thức ngành thời trang, nguyên tắc phối đồ, chất liệu và xu hướng. Suy luận HOÀN TOÀN TỰ DO bằng tiếng Việt, không bị ảnh hưởng bởi bất kỳ câu trả lời có sẵn nào.
2. Trả lời cuối cùng bằng tiếng Việt sau thẻ </think>: Rõ ràng, chuyên nghiệp, thực tế và có chiều sâu.

Định dạng bắt buộc:
<think>
[Quá trình suy luận chi tiết bằng tiếng Việt tại đây]
</think>
[Câu trả lời cuối cùng tại đây]"""

JUDGE_SYSTEM = """Bạn là Giáo sư Đầu ngành Thời trang kiêm Chuyên gia Thẩm định Dữ liệu AI khắt khe.
Nhiệm vụ của bạn là thực hiện Cross-check (Kiểm chứng chéo) gắt gao giữa câu trả lời gốc của dataset và câu trả lời mới từ AI cloud, rồi trả về JSON.

QUY TẮC THẨM ĐỊNH:
1. Tính Chính xác Kiến thức (Fashion Accuracy): A_Dataset có đúng không? Có bị ảo giác không?
2. Tính Đầy đủ & Văn phong (Completeness & Style): TUYỆT ĐỐI không mặc định A_Cloud luôn tốt hơn. Xem A_Cloud có bị ngắn gọn, thiếu ý, hoặc mất văn phong tư vấn chuyên nghiệp so với A_Dataset không?
3. Logic của Thẻ Thinking (Thinking Alignment): Thinking_Cloud có mạch lạc và hỗ trợ đúng cho câu trả lời tốt nhất không?

PHÂN LOẠI (chọn MỘT):
- "VERIFIED_EQUAL": Cả hai đúng kiến thức, tương đương về độ chi tiết.
- "DATASET_SUPERIOR": A_Dataset đúng VÀ chi tiết/đầy đủ hơn A_Cloud.
- "CLOUD_SUPERIOR": A_Dataset sai/ảo giác/quá tệ; A_Cloud đã sửa đúng hơn.
- "REJECTED": Q vô nghĩa, cả 2 câu trả lời đều rác.

ĐỊNH DẠNG TRẢ VỀ (JSON thuần, không markdown):
{"category": "...", "fact_check_notes": "Phân tích chi tiết lý do"}"""

def build_judge_user_message(question: str, a_dataset: str, thinking_cloud: str, a_cloud: str) -> str:
    return f"""Hãy thực hiện Cross-check cho cặp câu hỏi/câu trả lời sau:

===== CÂU HỎI (Q) =====
{question}

===== CÂU TRẢ LỜI GỐC (A_Dataset) =====
{a_dataset}

===== QUÁ TRÌNH SUY LUẬN CỦA CLOUD (Thinking_Cloud) =====
{thinking_cloud}

===== CÂU TRẢ LỜI MỚI CỦA CLOUD (A_Cloud) =====
{a_cloud}

Thực hiện kiểm chứng chéo theo 3 tiêu chí đã được hướng dẫn. Trả về JSON thuần."""

# --------------------------------------------------------------------------- #
#  Hàm helper nhận diện lỗi quota
# --------------------------------------------------------------------------- #
def is_quota_error(e: Exception, resp_text: str = "") -> bool:
    err_str = (str(e) + " " + resp_text).lower()
    
    # Nếu là lỗi concurrency (giới hạn RPM/QPS song song), đây không phải là hết hạn ngạch tài khoản
    if "concurrency" in err_str:
        return False
        
    if isinstance(e, requests.HTTPError) and e.response is not None:
        status_code = e.response.status_code
        if status_code in [429, 403]:
            # Đảm bảo không nhầm lẫn lỗi Rate/Concurrency Limit 429 thông thường với lỗi hết quota thật sự
            if "limit" in err_str or "rate" in err_str or "concurrency" in err_str:
                return False
            return True
            
    quota_keywords = [
        "outofquota",
        "allocationquotaexceeded",
        "billingspacenotenough",
        "insufficient balance",
        "quota exceeded"
    ]
    for kw in quota_keywords:
        if kw in err_str:
            return True
    return False

# --------------------------------------------------------------------------- #
#  Hàm gọi API có cơ chế Router tự động xoay vòng mô hình khi hết quota
# --------------------------------------------------------------------------- #
def call_api_with_router(messages: list, is_judge: bool = False, max_tokens: int = 4096, 
                         temperature: float = 0.7, timeout: int = 240, max_retries: int = 2) -> dict:
    global current_gen_idx, current_judge_idx
    
    models_list = JUDGE_MODELS if is_judge else GEN_MODELS
    
    while True:
        with index_lock:
            idx = current_judge_idx if is_judge else current_gen_idx
            if idx >= len(models_list):
                raise RuntimeError(f"Tất cả các mô hình trong danh sách {'Giám khảo' if is_judge else 'Sinh Reasoning'} đều đã báo lỗi hết quota!")
            model = models_list[idx]
            
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        last_err = None
        success = False
        resp_text = ""
        
        # In log nhẹ
        print(f"  [API Calls] [Thread={threading.current_thread().name}] Đang gọi mô hình: {model} ...", flush=True)
        
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    f"{BASE_URL}/chat/completions",
                    headers=HEADERS,
                    json=payload,
                    timeout=timeout,
                )
                resp_text = resp.text
                resp.raise_for_status()
                success = True
                break
            except Exception as e:
                last_err = e
                if is_quota_error(e, resp_text):
                    print(f"  ⚠️ [Thread={threading.current_thread().name}] Phát hiện lỗi hết quota trên mô hình {model}.", flush=True)
                    break
                if attempt < max_retries:
                    wait = 5 * attempt
                    time.sleep(wait)
        
        if success:
            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content", "") or ""
            usage = data.get("usage", {})
            thinking = message.get("reasoning_content", "") or ""
            
            if not thinking and "<think>" in content and "</think>" in content:
                think_start = content.index("<think>") + len("<think>")
                think_end = content.index("</think>")
                thinking = content[think_start:think_end].strip()
                content = content[think_end + len("</think>"):].strip()
                
            return {
                "thinking": thinking,
                "answer": content.strip(),
                "raw_content": content,
                "usage": usage,
                "model_used": model
            }
        else:
            if is_quota_error(last_err, resp_text):
                with index_lock:
                    # Kiểm tra lại xem thread khác đã tăng chỉ mục chưa để tránh tăng đúp
                    current_idx = current_judge_idx if is_judge else current_gen_idx
                    if current_idx == idx:
                        print(f"  🚨 [Thread={threading.current_thread().name}] Chuyển mô hình! Mô hình {model} báo HẾT QUOTA.", flush=True)
                        if is_judge:
                            current_judge_idx += 1
                        else:
                            current_gen_idx += 1
                time.sleep(2)
            else:
                print(f"  ❌ [Thread={threading.current_thread().name}] Lỗi kết nối / hệ thống nghiêm trọng trên mô hình {model}: {last_err}", flush=True)
                raise last_err

def call_judge(question: str, a_dataset: str, thinking_cloud: str, a_cloud: str) -> dict:
    user_msg = build_judge_user_message(question, a_dataset, thinking_cloud, a_cloud)
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]
    result = call_api_with_router(messages, is_judge=True, max_tokens=1024, temperature=0.3)
    raw_json = result["answer"].strip()
    
    if raw_json.startswith("```"):
        raw_json = "\n".join(raw_json.split("\n")[1:-1])
        
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        parsed = {"category": "PARSE_ERROR", "fact_check_notes": raw_json}
        
    parsed["_judge_usage"] = result["usage"]
    parsed["_judge_model"] = result["model_used"]
    return parsed

# --------------------------------------------------------------------------- #
#  Worker Task
# --------------------------------------------------------------------------- #
def process_row(row_idx, row, processed_ids):
    row_id = int(row["ID"])
    if row_id in processed_ids:
        return None
        
    question = str(row["translated_input"]).strip()
    a_dataset = str(row["translated_output"]).strip()
    tags = str(row.get("Tags", "N/A"))
    batch_id = row.get("batch_id", "N/A")
    
    print(f"\n  [Khởi chạy] ID={row_id} | Tags: {tags} | Batch: {batch_id}", flush=True)
    
    # Bước 1: Sinh Reasoning
    try:
        gen_result = call_api_with_router(
            messages=[
                {"role": "system", "content": REASONING_SYSTEM},
                {"role": "user", "content": question}
            ],
            is_judge=False,
            max_tokens=2048,
            temperature=0.7
        )
        thinking_cloud = gen_result["thinking"]
        a_cloud = gen_result["answer"]
        usage_gen = gen_result["usage"]
        model_gen = gen_result["model_used"]
    except Exception as e:
        print(f"  ❌ ID={row_id} lỗi Bước 1: {e}", flush=True)
        raise e
        
    # Bước 2: Giám khảo
    try:
        verdict = call_judge(question, a_dataset, thinking_cloud, a_cloud)
    except Exception as e:
        print(f"  ❌ ID={row_id} lỗi Bước 2: {e}", flush=True)
        raise e
        
    print(f"  ✅ [Hoàn thành] ID={row_id} | Giám khảo {verdict['_judge_model']} chấm: {verdict['category']}", flush=True)
    
    return {
        "row_index": row_idx,
        "id": row_id,
        "tags": tags,
        "batch_id": str(batch_id),
        "question": question,
        "a_dataset": a_dataset,
        "thinking_cloud": thinking_cloud,
        "a_cloud": a_cloud,
        "verdict": verdict,
        "usage_gen": usage_gen,
        "model_gen": model_gen
    }

# --------------------------------------------------------------------------- #
#  Main Pipeline logic
# --------------------------------------------------------------------------- #
def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    print("=" * 80)
    print("   BẮT ĐẦU PIPELINE GIAI ĐOẠN 5: ĐA LUỒNG SINH REASONING & CROSS-CHECK")
    print("=" * 80)
    
    if not STRATIFIED_CSV.exists():
        print(f"[FATAL] Không tìm thấy file dữ liệu phân tầng: {STRATIFIED_CSV}")
        sys.exit(1)
        
    df = pd.read_csv(STRATIFIED_CSV)
    total_rows = len(df)
    print(f"[INFO] Tổng số dòng dữ liệu cần xử lý: {total_rows}")
    
    processed_results = []
    processed_ids = set()
    
    if OUTPUT_LOG.exists():
        try:
            with open(OUTPUT_LOG, "r", encoding="utf-8") as f:
                processed_results = json.load(f)
                processed_ids = {item["id"] for item in processed_results}
            print(f"[INFO] Tìm thấy file checkpoint cũ. Đã tải {len(processed_ids)}/{total_rows} dòng.")
        except Exception as e:
            print(f"[WARNING] Lỗi khi đọc checkpoint cũ ({e}). Bắt đầu lại.")
            processed_results = []
            
    # Tải các tác vụ cần chạy
    tasks_to_run = []
    for idx, row in df.iterrows():
        if int(row["ID"]) not in processed_ids:
            tasks_to_run.append((idx, row))
            
    print(f"[INFO] Số lượng dòng cần xử lý trong phiên này: {len(tasks_to_run)}")
    
    if not tasks_to_run:
        print("[INFO] Đã xử lý toàn bộ dữ liệu. Kết thúc pipeline.")
        return
        
    # Chạy ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
        futures = {executor.submit(process_row, idx, row, processed_ids): row for idx, row in tasks_to_run}
        
        for future in as_completed(futures):
            try:
                res = future.result()
                if res is None:
                    continue
                    
                with checkpoint_lock:
                    processed_results.append(res)
                    processed_ids.add(res["id"])
                    
                    # Ghi checkpoint JSON
                    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
                        json.dump(processed_results, f, ensure_ascii=False, indent=2)
                        
                    # Ghi checkpoint CSV
                    final_rows = []
                    for item in processed_results:
                        cat = item["verdict"].get("category", "UNKNOWN")
                        if cat == "REJECTED":
                            continue
                            
                        ans_final = item["a_cloud"] if cat in ["VERIFIED_EQUAL", "CLOUD_SUPERIOR"] else item["a_dataset"]
                        formatted_thinking = f"<think>\n{item['thinking_cloud']}\n</think>\n{ans_final}"
                        
                        final_rows.append({
                            "ID": item["id"],
                            "Tags": item["tags"],
                            "batch_id": item["batch_id"],
                            "question": item["question"],
                            "final_response": formatted_thinking,
                            "category": cat,
                            "fact_check_notes": item["verdict"].get("fact_check_notes", ""),
                            "model_gen": item["model_gen"],
                            "model_judge": item["verdict"].get("_judge_model", "")
                        })
                        
                    if final_rows:
                        FINAL_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
                        pd.DataFrame(final_rows).to_csv(FINAL_OUTPUT_CSV, index=False)
                        
                    # Log nhẹ tiến độ
                    print(f"--> [Tiến độ hiện tại] Đã hoàn thành và lưu checkpoint cho {len(processed_ids)}/{total_rows} dòng.", flush=True)
                    
            except Exception as e:
                print(f"🚨 [LỖI THREAD] Một luồng gặp lỗi nghiêm trọng: {e}. Tiến hành dừng các tác vụ khác.", flush=True)
                executor.shutdown(wait=False, cancel_futures=True)
                sys.exit(1)
                
    print("\n" + "=" * 80)
    print("   HOÀN THÀNH TOÀN BỘ PIPELINE ĐA LUỒNG GIAI ĐOẠN 5")
    print("=" * 80)
    print(f"Tổng số dòng đã xử lý: {len(processed_results)}")
    print(f"File log chi tiết: {OUTPUT_LOG}")
    print(f"File kết quả cuối cùng: {FINAL_OUTPUT_CSV}")
    
if __name__ == "__main__":
    main()
