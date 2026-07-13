# -*- coding: utf-8 -*-
"""
polish_dataset_answers.py — Đánh bóng văn phong cho A_Dataset
============================================================
"""

import json
import sys
import time
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import threading

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
from configs.paths import STRATIFIED_CSV, DATA_REASONING, DATA_FINAL

load_dotenv(ROOT / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
from src.reasoning_generation.ver_2.run_reasoning_pipeline_openrouter import (
    call_api, API_KEYS, OUTPUT_LOG, FINAL_OUTPUT_CSV
)

POLISH_SYSTEM = """Bạn là chuyên gia tư vấn thời trang Việt Nam chuyên nghiệp.
Nhiệm vụ của bạn là đọc một Câu hỏi, phần Tư duy của chuyên gia, và Câu trả lời gốc (vốn đang bị sượng văn phong hoặc mang tính dịch thuật).
Hãy viết lại câu trả lời gốc này thành một phiên bản trôi chảy, mạch lạc, tự nhiên nhất theo phong cách bản xứ Việt Nam.

QUY TẮC BẮT BUỘC:
1. KHÔNG được bịa đặt hay thêm bớt thông tin thực tế/kiến thức chuyên môn so với câu trả lời gốc.
2. Giữ nguyên các thông tin kỹ thuật, số liệu, hoặc lời khuyên chính xác từ câu trả lời gốc.
3. Chỉ viết lại câu trả lời mượt mà hơn, không thêm thẻ <think> hay lời dẫn ngoài lề.
4. Viết bằng tiếng Việt tự nhiên và chuyên nghiệp."""

VERIFY_SYSTEM = """Bạn là Chuyên gia Kiểm định Dữ liệu AI. 
Hãy so sánh Câu trả lời Gốc và Câu trả lời Đã Đánh Bóng để kiểm tra xem có hiện tượng ảo giác hay sai lệch kiến thức/thông tin hay không.

YÊU CẦU:
1. Xác định xem Câu trả lời Đã Đánh Bóng có giữ nguyên 100% các dữ kiện, thông tin và kiến thức cốt lõi từ Câu trả lời Gốc hay không.
2. Nếu Câu trả lời Đã Đánh Bóng tự chế thêm thông tin mới, hoặc làm sai lệch thông tin gốc, trả về is_safe = false.
3. Trả về JSON thuần (không markdown):
{"is_safe": true/false, "explanation": "lý do ngắn gọn"}"""

def polish_answer(question, thinking, original_answer, api_key, rejections=None):
    prompt = f"""===== CÂU HỎI =====
{question}

===== QUÁ TRÌNH TƯ DUY =====
{thinking}

===== CÂU TRẢ LỜI GỐC (SƯỢNG) =====
{original_answer}
"""
    if rejections:
        prompt += "\n===== CÁC LÝ DO BỊ TỪ CHỐI Ở LẦN THỬ TRƯỚC (BẮT BUỘC RÚT KINH NGHIỆM) =====\n"
        for idx, rej in enumerate(rejections, 1):
            prompt += f"{idx}. {rej}\n"
        prompt += "\nHãy tránh mắc các lỗi trên trong lần viết lại này.\n"

    prompt += "\nHãy viết lại câu trả lời trên mượt mà và tự nhiên hơn:"
    
    res = call_api(
        messages=[
            {"role": "system", "content": POLISH_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2000,
        temperature=0.4,
        api_key=api_key
    )
    return res["content"]

def verify_polished(original_answer, polished_answer, api_key):
    prompt = f"""===== CÂU TRẢ LỜI GỐC =====
{original_answer}

===== CÂU TRẢ LỜI ĐÃ ĐÁNH BÓNG =====
{polished_answer}

Hãy so sánh và đánh giá tính chính xác thông tin:"""

    res = call_api(
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2500,
        temperature=0.1,
        api_key=api_key
    )
    raw = res["content"]
    print(f"    [Verify Debug] RAW CONTENT:\n{raw}\n", flush=True)
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw.replace("```json", "").replace("```", "")
    try:
        parsed = json.loads(raw)
        return parsed
    except Exception:
        import re
        safe_m = re.search(r'"is_safe"\s*:\s*(true|false)', raw)
        is_safe = (safe_m.group(1) == "true") if safe_m else False
        return {"is_safe": is_safe, "explanation": raw[:200]}

def polish_row(item, api_key):
    question = item["question"]
    thinking = item.get("thinking_reverse", "")
    original_answer = item.get("a_final", "")
    rejections = item.get("polish_rejections", [])
    
    if not original_answer:
        return item, False

    try:
        # Step 1: Polish
        polished = polish_answer(question, thinking, original_answer, api_key, rejections)
        print(f"    [Polish Debug] POLISHED ANSWER (len={len(polished)}):\n{polished}\n", flush=True)
        time.sleep(4)
        
        # Step 2: Verify
        verdict = verify_polished(original_answer, polished, api_key)
        time.sleep(4)
        
        if verdict.get("is_safe") is True:
            item["a_final"] = polished
            item["final_response"] = f"<think>\n{thinking}\n</think>\n{polished}"
            item["polish_status"] = "SUCCESS"
            item["polish_explanation"] = verdict.get("explanation", "")
            return item, True
        else:
            explanation = verdict.get("explanation", "Bị từ chối bởi bộ thẩm định.")
            if "polish_rejections" not in item:
                item["polish_rejections"] = []
            item["polish_rejections"].append(explanation)
            item["polish_status"] = "REJECTED_BY_VERIFIER"
            item["polish_explanation"] = explanation
            return item, False
    except Exception as e:
        print(f"  ❌ Lỗi khi đánh bóng dòng {item['id']}: {e}")
        return item, False

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Chạy thử nghiệm trên 3 dòng")
    args = parser.parse_args()

    if not OUTPUT_LOG.exists():
        print(f"Không tìm thấy file log: {OUTPUT_LOG}")
        return
        
    with open(OUTPUT_LOG, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Lọc ra các dòng cần đánh bóng
    dataset_rows = [item for item in data if item.get("a_final_source") == "A_Dataset"]
    print(f"Tổng số dòng lấy nguồn A_Dataset cần đánh bóng: {len(dataset_rows)}")
    
    if args.test:
        print("\n--- BẮT ĐẦU CHẠY THỬ NGHIỆM TRÊN 3 DÒNG MẪU ---")
        test_rows = dataset_rows[:3]
        for idx, row in enumerate(test_rows):
            api_key = API_KEYS[idx % len(API_KEYS)]
            print(f"\n[Test] ID={row['id']} | Key Index: {idx % len(API_KEYS)}")
            print(f"  Gốc: {row.get('a_final', '')[:100]}...")
            updated, success = polish_row(row, api_key)
            if success:
                print(f"  ✅ Đánh bóng thành công!")
                print(f"  Mới: {updated['a_final'][:150]}...")
            else:
                print(f"  ❌ Đánh bóng bị từ chối/thất bại. Lý do: {updated.get('polish_explanation')}")
        print("\n--- KẾT THÚC CHẠY THỬ NGHIỆM ---")
        return
        
    # Chạy full đa đợt (Multi-pass loop) với đa luồng ThreadPoolExecutor (max_workers=2)
    pass_num = 1
    max_attempts_per_row = 5
    N_WORKERS = 4
    save_lock = threading.Lock()
    
    while True:
        # Lọc ra các dòng cần đánh bóng (chưa SUCCESS và chưa đạt giới hạn tối đa)
        to_polish_indices = []
        for i, item in enumerate(data):
            if item.get("a_final_source") == "A_Dataset":
                status = item.get("polish_status")
                attempts = len(item.get("polish_rejections", []))
                if status != "SUCCESS" and attempts < max_attempts_per_row:
                    to_polish_indices.append(i)
                    
        if not to_polish_indices:
            print("\n🎉 HOÀN TẤT: Không còn dòng nào cần đánh bóng (Tất cả thành công hoặc đạt giới hạn thử tối đa)!")
            break
            
        print(f"\n🚀 === BẮT ĐẦU ĐỢT CHẠY THỨ {pass_num} (Còn {len(to_polish_indices)} dòng cần xử lý) ===")
        
        success_count = 0
        fail_count = 0
        
        def process_index(job_idx, data_idx):
            nonlocal success_count, fail_count
            item = data[data_idx]
            api_key = API_KEYS[job_idx % len(API_KEYS)]
            attempts = len(item.get("polish_rejections", []))
            
            with save_lock:
                print(f"[{job_idx+1}/{len(to_polish_indices)}] ID={item['id']} | Lần thử thứ {attempts + 1} | Key Index: {job_idx % len(API_KEYS)}...")
            
            updated_item, success = polish_row(item, api_key)
            
            with save_lock:
                data[data_idx] = updated_item
                if success:
                    success_count += 1
                    print(f"  ✅ ID={item['id']}: Đánh bóng THÀNH CÔNG!")
                else:
                    fail_count += 1
                    print(f"  ❌ ID={item['id']}: Đánh bóng THẤT BẠI. Lý do: {updated_item.get('polish_explanation')}")
                
                # Lưu checkpoint lũy tiến sau mỗi dòng
                with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
                # Ghi CSV lũy tiến sau mỗi dòng
                final_rows = []
                for r in data:
                    if r.get("final_response") is None:
                        continue
                    cat = r.get("verdict", {}).get("category", "UNKNOWN")
                    final_rows.append({
                        "ID": r["id"],
                        "Tags": r["tags"],
                        "batch_id": r["batch_id"],
                        "question": r["question"],
                        "final_response": r["final_response"],
                        "category": cat,
                        "a_final_source": r.get("a_final_source", ""),
                        "fact_check_notes": r.get("verdict", {}).get("fact_check_notes", ""),
                        "api_key_used": r.get("api_key_used", ""),
                    })
                pd.DataFrame(final_rows).to_csv(FINAL_OUTPUT_CSV, index=False)
        
        # Chạy song song 2 luồng tương ứng với 2 key vật lý
        with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
            executor.map(
                lambda pair: process_index(pair[0], pair[1]),
                enumerate(to_polish_indices)
            )
            
        print(f"Kết thúc Đợt {pass_num}! Đợt này: Thành công {success_count}, Thất bại/Bị từ chối: {fail_count}")
        pass_num += 1

if __name__ == "__main__":
    main()
