# -*- coding: utf-8 -*-
"""
run_reasoning_pipeline_openrouter.py — Ver 3: Full 3-Step Pipeline (1488 dòng)
================================================================================
Thiết kế Ver 3:
  Step 1: Gen Answer (KHÔNG reasoning) → A_Cloud
  Step 2: Judge gọn (2 tiêu chí) → verdict
  Step 3: Reverse Prompting → Thinking_Reverse (100% tiếng Việt)

Cơ chế:
  - 2 API Keys round-robin theo row_idx → mỗi row dùng 1 key nhất quán
  - N_WORKERS = 6 (3 per key) → throughput ~2x so với Ver 2
  - Checkpoint JSON + CSV lũy tiến sau mỗi row hoàn thành
  - Thread-safe với checkpoint_lock

Cách chạy:
  $env:PYTHONIOENCODING='utf-8'
  python src/reasoning_generation/ver_2/run_reasoning_pipeline_openrouter.py
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

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
from configs.paths import STRATIFIED_CSV, DATA_REASONING, DATA_FINAL

load_dotenv(ROOT / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "tencent/hy3:free"
N_WORKERS = 6  # 3 per key

API_KEYS = [
    os.getenv("OPENROUTER_API_KEY"),
    os.getenv("OPENROUTER_API_KEY_2"),
]
API_KEYS = [k for k in API_KEYS if k]

if not API_KEYS:
    print("[FATAL] Không tìm thấy OPENROUTER_API_KEY trong .env")
    sys.exit(1)

OUTPUT_LOG = DATA_REASONING / "reasoning_generation_v3_log.json"
FINAL_OUTPUT_CSV = DATA_FINAL / "final_distilled_reasoning_1488_v3.csv"

checkpoint_lock = threading.Lock()

# ── Prompt Templates ──────────────────────────────────────────────────────────

GEN_SYSTEM = "Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt chuyên nghiệp, ngắn gọn và súc tích."

JUDGE_SYSTEM = """Bạn là Chuyên gia Thẩm định Dữ liệu AI về thời trang. Nhiệm vụ: so sánh 2 câu trả lời và trả về JSON.

QUY TẮC (2 tiêu chí):
1. Tính Chính xác Kiến thức: Câu nào đúng hơn về kiến thức thời trang? Câu nào bị ảo giác?
2. Tính Đầy đủ & Văn phong: Câu nào chi tiết, đầy đủ, chuyên nghiệp hơn? KHÔNG mặc định A_Cloud luôn tốt hơn.

PHÂN LOẠI (chọn MỘT):
- "VERIFIED_EQUAL": Cả hai đúng và tương đương.
- "CLOUD_SUPERIOR": A_Cloud đúng hơn / đầy đủ hơn rõ rệt.
- "DATASET_SUPERIOR": A_Dataset đúng hơn / đầy đủ hơn rõ rệt.
- "REJECTED": Câu hỏi vô nghĩa hoặc cả 2 đều sai.

OUTPUT (JSON thuần, không markdown):
{"category": "...", "fact_check_notes": "lý do ngắn gọn"}"""

REVERSE_SYSTEM = """Bạn là chuyên gia tư vấn thời trang Việt Nam chuyên nghiệp.
Được cung cấp một câu hỏi và câu trả lời thời trang chuẩn, hãy tái hiện quá trình TƯ DUY của chuyên gia dẫn đến câu trả lời đó.

YÊU CẦU BẮT BUỘC:
- Viết HOÀN TOÀN bằng tiếng Việt
- Thể hiện luồng tư duy: hiểu yêu cầu → xác định vấn đề cốt lõi → xây dựng giải pháp
- KHÔNG lặp nguyên văn câu trả lời trong phần tư duy
- KHÔNG dùng thẻ <think> hay headers markdown (##, ###)
- Độ dài: 150-400 từ, đủ thể hiện tư duy mà không dông dài"""


# ── API Call Helper ───────────────────────────────────────────────────────────

def make_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/fashion-ai-pipeline",
        "X-Title": "Fashion AI Pipeline v3",
    }


def call_api(messages: list, max_tokens: int, temperature: float,
              api_key: str, timeout: int = 120, max_retries: int = 5) -> dict:
    """Gọi OpenRouter API không có reasoning flag (Ver 3 default)."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    headers = make_headers(api_key)
    last_err = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if not content:
                raise ValueError("API returned empty content")
            break
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                wait = min(8 * attempt, 30)
                print(f"  ⚠️ [retry {attempt}] {e} → wait {wait}s", flush=True)
                time.sleep(wait)
            else:
                raise last_err

    usage = data.get("usage", {})
    return {"content": content, "usage": usage}


# ── Step Functions ─────────────────────────────────────────────────────────────

def step1_gen_answer(question: str, api_key: str) -> dict:
    return call_api(
        messages=[
            {"role": "system", "content": GEN_SYSTEM},
            {"role": "user", "content": question},
        ],
        max_tokens=1500,
        temperature=0.7,
        api_key=api_key,
    )


def step2_judge(question: str, a_dataset: str, a_cloud: str, api_key: str) -> dict:
    user_msg = f"""Hãy so sánh 2 câu trả lời thời trang sau:

===== CÂU HỎI =====
{question}

===== A_Dataset (câu trả lời gốc) =====
{a_dataset}

===== A_Cloud (câu trả lời AI) =====
{a_cloud}

Thực hiện so sánh theo 2 tiêu chí. Trả về JSON thuần."""

    result = call_api(
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=2500,   # FIX: HY3 think nội bộ ~1000-1500 tokens
        temperature=0.3,
        api_key=api_key,
    )
    raw = result["content"]
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw.replace("```json", "").replace("```", "")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Regex rescue logic
        import re
        cat_match = re.search(r'"category"\s*:\s*"([A-Z_]+)"', raw)
        note_match = re.search(r'"fact_check_notes"\s*:\s*"([^"]+)"', raw)
        
        category = "PARSE_ERROR"
        if cat_match and cat_match.group(1) in ("VERIFIED_EQUAL", "CLOUD_SUPERIOR", "DATASET_SUPERIOR", "REJECTED"):
            category = cat_match.group(1)
            
        notes = note_match.group(1) if note_match else raw[:300]
        parsed = {"category": category, "fact_check_notes": notes, "raw_judge_response": raw}
    parsed["_usage"] = result["usage"]
    return parsed


def step3_reverse_prompt(question: str, a_final: str, api_key: str) -> dict:
    user_msg = f"""Câu hỏi khách hàng:
{question}

Câu trả lời chuyên gia:
{a_final}

Hãy tái hiện QUÁ TRÌNH TƯ DUY (bằng tiếng Việt) của chuyên gia dẫn đến câu trả lời trên. Chỉ viết phần tư duy, không lặp lại câu trả lời."""

    return call_api(
        messages=[
            {"role": "system", "content": REVERSE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=4000,   # FIX: HY3 think nội bộ ~1500-1800 tokens
        temperature=0.6,
        api_key=api_key,
    )


# ── Worker ────────────────────────────────────────────────────────────────────

def process_row(row_idx: int, row, processed_ids: set) -> dict | None:
    row_id = int(row["ID"])
    if row_id in processed_ids:
        return None

    question = str(row["translated_input"]).strip()
    a_dataset = str(row["translated_output"]).strip()
    tags = str(row.get("Tags", "N/A"))
    batch_id = str(row.get("batch_id", "N/A"))

    # Key rotation: mỗi row dùng 1 key nhất quán cho cả 3 steps
    api_key = API_KEYS[row_idx % len(API_KEYS)]
    key_label = f"Key_{(row_idx % len(API_KEYS)) + 1}"

    print(f"\n  [Start] ID={row_id} | {key_label} | Tags: {tags[:40]}", flush=True)

    record = {
        "row_index": row_idx,
        "id": row_id,
        "tags": tags,
        "batch_id": batch_id,
        "question": question,
        "a_dataset": a_dataset,
        "api_key_used": key_label,
    }

    # Step 1: Gen Answer
    try:
        s1 = step1_gen_answer(question, api_key)
        a_cloud = s1["content"]
        record["a_cloud"] = a_cloud
        record["usage_step1"] = s1["usage"]
        print(f"  [S1 ✓] ID={row_id} A_Cloud={len(a_cloud)}c tokens={s1['usage'].get('completion_tokens')}", flush=True)
    except Exception as e:
        print(f"  [S1 ✗] ID={row_id} {e}", flush=True)
        raise

    time.sleep(3)

    # Step 2: Judge
    try:
        verdict = step2_judge(question, a_dataset, a_cloud, api_key)
        category = verdict.get("category", "PARSE_ERROR")
        record["verdict"] = verdict
        print(f"  [S2 ✓] ID={row_id} verdict={category}", flush=True)
    except Exception as e:
        print(f"  [S2 ✗] ID={row_id} {e}", flush=True)
        raise

    time.sleep(3)

    # Step 3: Reverse Prompting
    if category == "REJECTED":
        print(f"  [S3 -] ID={row_id} REJECTED → skip", flush=True)
        record["a_final"] = None
        record["a_final_source"] = "REJECTED"
        record["thinking_reverse"] = None
        record["final_response"] = None
    else:
        a_final_source = "A_Cloud" if category in ("VERIFIED_EQUAL", "CLOUD_SUPERIOR") else "A_Dataset"
        a_final = a_cloud if a_final_source == "A_Cloud" else a_dataset
        record["a_final"] = a_final
        record["a_final_source"] = a_final_source

        try:
            s3 = step3_reverse_prompt(question, a_final, api_key)
            thinking_reverse = s3["content"]
            record["thinking_reverse"] = thinking_reverse
            record["usage_step3"] = s3["usage"]
            record["final_response"] = f"<think>\n{thinking_reverse}\n</think>\n{a_final}"
            print(f"  [S3 ✓] ID={row_id} Thinking={len(thinking_reverse)}c src={a_final_source}", flush=True)
        except Exception as e:
            print(f"  [S3 ✗] ID={row_id} {e}", flush=True)
            raise

    return record


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    print("=" * 80)
    print("   PIPELINE VER 3: GEN → JUDGE → REVERSE PROMPTING (1488 dòng)")
    print(f"   Model: {MODEL} | Keys: {len(API_KEYS)} | Workers: {N_WORKERS}")
    print("=" * 80)

    if not STRATIFIED_CSV.exists():
        print(f"[FATAL] Không tìm thấy: {STRATIFIED_CSV}")
        sys.exit(1)

    df = pd.read_csv(STRATIFIED_CSV)
    total_rows = len(df)
    print(f"[INFO] Tổng số dòng: {total_rows}")

    # Load checkpoint
    processed_results = []
    processed_ids = set()
    if OUTPUT_LOG.exists():
        try:
            with open(OUTPUT_LOG, "r", encoding="utf-8") as f:
                processed_results = json.load(f)
                processed_ids = {item["id"] for item in processed_results}
            print(f"[INFO] Đã tải checkpoint: {len(processed_ids)}/{total_rows} dòng")
        except Exception as e:
            print(f"[WARNING] Lỗi đọc checkpoint: {e}. Bắt đầu lại.")

    tasks_to_run = [(idx, row) for idx, row in df.iterrows() if int(row["ID"]) not in processed_ids]
    print(f"[INFO] Cần xử lý: {len(tasks_to_run)} dòng")

    if not tasks_to_run:
        print("[INFO] Đã xử lý toàn bộ. Kết thúc.")
        return

    # ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
        futures = {
            executor.submit(process_row, idx, row, processed_ids): row
            for idx, row in tasks_to_run
        }

        for future in as_completed(futures):
            try:
                res = future.result()
                if res is None:
                    continue

                with checkpoint_lock:
                    processed_results.append(res)
                    processed_ids.add(res["id"])

                    # Checkpoint JSON
                    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
                        json.dump(processed_results, f, ensure_ascii=False, indent=2)

                    # Checkpoint CSV
                    final_rows = []
                    for item in processed_results:
                        if item.get("final_response") is None:
                            continue
                        cat = item.get("verdict", {}).get("category", "UNKNOWN")
                        final_rows.append({
                            "ID": item["id"],
                            "Tags": item["tags"],
                            "batch_id": item["batch_id"],
                            "question": item["question"],
                            "final_response": item["final_response"],
                            "category": cat,
                            "a_final_source": item.get("a_final_source", ""),
                            "fact_check_notes": item.get("verdict", {}).get("fact_check_notes", ""),
                            "api_key_used": item.get("api_key_used", ""),
                        })

                    if final_rows:
                        FINAL_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
                        pd.DataFrame(final_rows).to_csv(FINAL_OUTPUT_CSV, index=False)

                    done = len(processed_ids)
                    print(f"--> [Tiến độ] {done}/{total_rows} ({done/total_rows*100:.1f}%)", flush=True)

            except Exception as e:
                print(f"🚨 [LỖI THREAD] {e}", flush=True)
                executor.shutdown(wait=False, cancel_futures=True)
                sys.exit(1)

    # Final stats
    print("\n" + "=" * 80)
    print("   HOÀN THÀNH PIPELINE VER 3")
    print("=" * 80)
    print(f"Tổng đã xử lý: {len(processed_results)}")
    print(f"Log: {OUTPUT_LOG}")
    print(f"CSV: {FINAL_OUTPUT_CSV}")

    # Verdict distribution
    category_counts = {}
    source_counts = {}
    for r in processed_results:
        cat = r.get("verdict", {}).get("category", "UNKNOWN")
        src = r.get("a_final_source", "UNKNOWN")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        source_counts[src] = source_counts.get(src, 0) + 1

    print("\n📊 VERDICT DISTRIBUTION:")
    emoji = {"VERIFIED_EQUAL": "✅", "CLOUD_SUPERIOR": "🔄", "DATASET_SUPERIOR": "📌",
             "REJECTED": "🗑️", "PARSE_ERROR": "❓", "UNKNOWN": "❔"}
    for cat, cnt in sorted(category_counts.items()):
        pct = cnt / len(processed_results) * 100
        print(f"  {emoji.get(cat,'?')} {cat}: {cnt} ({pct:.1f}%)")

    print("\n📂 A_FINAL SOURCE:")
    for src, cnt in sorted(source_counts.items()):
        pct = cnt / len(processed_results) * 100
        print(f"  {src}: {cnt} ({pct:.1f}%)")

    # Token summary
    total_tok = {"step1_in": 0, "step1_out": 0, "step2_in": 0, "step2_out": 0, "step3_in": 0, "step3_out": 0}
    for r in processed_results:
        u1 = r.get("usage_step1", {})
        u2 = r.get("verdict", {}).get("_usage", {})
        u3 = r.get("usage_step3", {})
        total_tok["step1_in"] += u1.get("prompt_tokens", 0)
        total_tok["step1_out"] += u1.get("completion_tokens", 0)
        total_tok["step2_in"] += u2.get("prompt_tokens", 0)
        total_tok["step2_out"] += u2.get("completion_tokens", 0)
        total_tok["step3_in"] += u3.get("prompt_tokens", 0)
        total_tok["step3_out"] += u3.get("completion_tokens", 0)

    print(f"\n💰 TỔNG TOKENS:")
    print(f"  Step1: {total_tok['step1_in']:,} in / {total_tok['step1_out']:,} out")
    print(f"  Step2: {total_tok['step2_in']:,} in / {total_tok['step2_out']:,} out")
    print(f"  Step3: {total_tok['step3_in']:,} in / {total_tok['step3_out']:,} out")
    grand = sum(total_tok.values())
    print(f"  TOTAL: {grand:,} tokens | Chi phí: MIỄN PHÍ (free tier)")


if __name__ == "__main__":
    main()
