# -*- coding: utf-8 -*-
"""
run_pilot_run_openrouter.py — Ver 3: Pilot Run 3-Step Pipeline
================================================================
Thiết kế Ver 3 (thay thế Ver 2):
  Step 1: Gen Answer (KHÔNG reasoning) → A_Cloud
  Step 2: Judge gọn (2 tiêu chí, không Thinking block) → verdict
  Step 3: Reverse Prompting trên A_Final → Thinking_Reverse tiếng Việt

Cải tiến so với Ver 2:
  - Bỏ "reasoning: enabled" ở Step 1 → tránh bilingual thinking, nhẹ hơn 60%
  - Judge prompt gọn hơn (~1200 chars vs ~5000 chars cũ)
  - Thinking_Reverse 100% tiếng Việt, kiểm soát được
  - Hỗ trợ 2 API keys (round-robin theo row index)

Cách chạy:
  $env:PYTHONIOENCODING='utf-8'
  python src/reasoning_generation/ver_2/run_pilot_run_openrouter.py
"""

import json
import os
import sys
import time
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
from configs.paths import STRATIFIED_CSV, DATA_REASONING

load_dotenv(ROOT / ".env")

# 2 API Keys — round-robin
API_KEYS = [
    os.getenv("OPENROUTER_API_KEY"),
    os.getenv("OPENROUTER_API_KEY_2"),
]
API_KEYS = [k for k in API_KEYS if k]  # lọc None nếu thiếu key

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "tencent/hy3:free"
OUTPUT_LOG = DATA_REASONING / "pilot_run_v3_log.json"

if not API_KEYS:
    print("[FATAL] Không tìm thấy OPENROUTER_API_KEY trong .env")
    sys.exit(1)

print(f"[INFO] Loaded {len(API_KEYS)} API key(s)")

# ── Prompt Templates ─────────────────────────────────────────────────────────

# Step 1: System prompt tối giản — chỉ vai trò, không inject context phức tạp
GEN_SYSTEM = "Bạn là chuyên gia tư vấn thời trang Việt Nam. Trả lời câu hỏi bằng tiếng Việt chuyên nghiệp, ngắn gọn và súc tích."

# Step 2: Judge chỉ 2 tiêu chí — bỏ tiêu chí Thinking Alignment của Ver 2
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

# Step 3: Reverse prompting — sinh thinking tiếng Việt từ Q + A_Final
REVERSE_SYSTEM = """Bạn là chuyên gia tư vấn thời trang Việt Nam chuyên nghiệp.
Được cung cấp một câu hỏi và câu trả lời thời trang chuẩn, hãy tái hiện quá trình TƯ DUY của chuyên gia dẫn đến câu trả lời đó.

YÊU CẦU BẮT BUỘC:
- Viết HOÀN TOÀN bằng tiếng Việt
- Thể hiện luồng tư duy: hiểu yêu cầu → xác định vấn đề cốt lõi → xây dựng giải pháp
- KHÔNG lặp nguyên văn câu trả lời trong phần tư duy
- KHÔNG dùng thẻ <think> hay headers markdown (##, ###)
- Độ dài: 150-400 từ, đủ thể hiện tư duy mà không dông dài"""


def make_headers(key: str) -> dict:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/fashion-ai-pipeline",
        "X-Title": "Fashion AI Pipeline v3",
    }


def call_api(messages: list, max_tokens: int, temperature: float,
             api_key: str, use_reasoning: bool = False,
             timeout: int = 120, max_retries: int = 3) -> dict:
    """Gọi OpenRouter API. use_reasoning=False theo mặc định (Ver 3)."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if use_reasoning:
        payload["reasoning"] = {"enabled": True}

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
            break
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                wait = 5 * attempt
                print(f"    Retry {attempt}/{max_retries} sau {wait}s: {e}")
                time.sleep(wait)
            else:
                raise last_err

    data = resp.json()
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    usage = data.get("usage", {})
    return {"content": content, "usage": usage}


# ── Step 1: Gen Answer ────────────────────────────────────────────────────────

def step1_gen_answer(question: str, api_key: str) -> dict:
    """Sinh A_Cloud từ Q. KHÔNG dùng reasoning flag."""
    result = call_api(
        messages=[
            {"role": "system", "content": GEN_SYSTEM},
            {"role": "user", "content": question},
        ],
        max_tokens=1500,
        temperature=0.7,
        api_key=api_key,
        use_reasoning=False,  # ← Ver 3: không cần reasoning
    )
    return result


# ── Step 2: Judge ─────────────────────────────────────────────────────────────

def step2_judge(question: str, a_dataset: str, a_cloud: str, api_key: str) -> dict:
    """So sánh A_Cloud vs A_Dataset. Prompt gọn — không có Thinking block."""
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
        max_tokens=2500,   # FIX: HY3 think nội bộ ~1000-1500 tokens, cần đủ chỗ cho JSON
        temperature=0.3,
        api_key=api_key,
        use_reasoning=False,
    )

    raw = result["content"]
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw.replace("```json", "").replace("```", "")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"category": "PARSE_ERROR", "fact_check_notes": raw[:300]}

    parsed["_usage"] = result["usage"]
    return parsed


# ── Step 3: Reverse Prompting ─────────────────────────────────────────────────

def step3_reverse_prompt(question: str, a_final: str, api_key: str) -> dict:
    """Sinh Thinking_Reverse bằng tiếng Việt từ Q + A_Final."""
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
        max_tokens=4000,   # FIX: HY3 think nội bộ ~1500-1800 tokens, cần đủ chỗ cho thinking text
        temperature=0.6,
        api_key=api_key,
        use_reasoning=False,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    print("=" * 70)
    print("🚀 PILOT RUN VER 3 — 3-STEP PIPELINE (Gen → Judge → Reverse)")
    print(f"   Model: {MODEL} | Keys: {len(API_KEYS)}")
    print("=" * 70)

    df = pd.read_csv(STRATIFIED_CSV).head(3)
    results = []

    for i, (idx, row) in enumerate(df.iterrows()):
        question = str(row["translated_input"]).strip()
        a_dataset = str(row["translated_output"]).strip()
        tags = str(row.get("Tags", "N/A"))
        row_id = int(row["ID"])

        # Key rotation theo row index
        api_key = API_KEYS[i % len(API_KEYS)]
        key_label = f"Key_{(i % len(API_KEYS)) + 1}"

        print(f"\n{'─'*65}")
        print(f"  Row {i+1}/3 | ID={row_id} | Tags: {tags} | {key_label}")
        print(f"  Q: {question[:90]}...")
        print(f"{'─'*65}")

        record = {
            "id": row_id,
            "tags": tags,
            "question": question,
            "a_dataset": a_dataset,
            "api_key_used": key_label,
        }

        # ── Step 1: Gen Answer ──
        print("  [Step 1] Sinh A_Cloud (no reasoning)...")
        try:
            s1 = step1_gen_answer(question, api_key)
            a_cloud = s1["content"]
            record["a_cloud"] = a_cloud
            record["usage_step1"] = s1["usage"]
            tok1 = s1["usage"]
            print(f"  ✅ A_Cloud: {len(a_cloud)} chars | tokens: {tok1.get('prompt_tokens')}→{tok1.get('completion_tokens')}")
        except Exception as e:
            print(f"  ❌ Step 1 lỗi: {e}")
            record["error"] = f"step1: {e}"
            results.append(record)
            continue

        time.sleep(4)

        # ── Step 2: Judge ──
        print("  [Step 2] Thẩm định A_Cloud vs A_Dataset...")
        try:
            verdict = step2_judge(question, a_dataset, a_cloud, api_key)
            category = verdict.get("category", "?")
            notes = verdict.get("fact_check_notes", "")[:120]
            record["verdict"] = verdict
            tok2 = verdict.get("_usage", {})
            print(f"  ✅ Verdict: {category} | tokens: {tok2.get('prompt_tokens')}→{tok2.get('completion_tokens')}")
            print(f"     Notes: {notes}")
        except Exception as e:
            print(f"  ❌ Step 2 lỗi: {e}")
            record["verdict"] = {"category": "ERROR", "fact_check_notes": str(e)}
            category = "ERROR"

        time.sleep(4)

        # ── Step 3: Reverse Prompting ──
        if category == "REJECTED":
            print("  [Step 3] Bỏ qua (REJECTED)")
            record["a_final"] = None
            record["thinking_reverse"] = None
            record["final_response"] = None
        else:
            a_final = a_cloud if category in ("VERIFIED_EQUAL", "CLOUD_SUPERIOR") else a_dataset
            record["a_final_source"] = "A_Cloud" if category in ("VERIFIED_EQUAL", "CLOUD_SUPERIOR") else "A_Dataset"
            record["a_final"] = a_final

            print(f"  [Step 3] Reverse Prompting trên {record['a_final_source']}...")
            try:
                s3 = step3_reverse_prompt(question, a_final, api_key)
                thinking_reverse = s3["content"]
                record["thinking_reverse"] = thinking_reverse
                record["usage_step3"] = s3["usage"]
                tok3 = s3["usage"]
                final_response = f"<think>\n{thinking_reverse}\n</think>\n{a_final}"
                record["final_response"] = final_response
                print(f"  ✅ Thinking: {len(thinking_reverse)} chars | tokens: {tok3.get('prompt_tokens')}→{tok3.get('completion_tokens')}")
            except Exception as e:
                print(f"  ❌ Step 3 lỗi: {e}")
                record["thinking_reverse"] = None
                record["final_response"] = None

        results.append(record)
        if i < 2:
            time.sleep(5)

    # Ghi log
    OUTPUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"✅ Pilot Run Ver 3 hoàn thành! Log: {OUTPUT_LOG}")
    print("\n📊 TỔNG KẾT:")
    for r in results:
        cat = r.get("verdict", {}).get("category", "N/A")
        src = r.get("a_final_source", "N/A")
        think_len = len(r.get("thinking_reverse") or "")
        print(f"  ID={r['id']}: {cat} → A_Final={src} | Thinking={think_len} chars")
    print("=" * 70)


if __name__ == "__main__":
    main()
