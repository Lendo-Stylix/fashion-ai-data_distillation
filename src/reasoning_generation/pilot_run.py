# -*- coding: utf-8 -*-
"""
pilot_run.py — Giai đoạn 5: Chạy thử nghiệm Pilot Run (3 dòng đầu tiên)
=========================================================================
Mục tiêu:
  1. Trích xuất 3 dòng đầu tiên từ stratified_1488.csv.
  2. Gọi API qwen3.7-plus (DashScope) để sinh Thinking_Cloud & A_Cloud.
  3. Gọi lại API (đóng vai Giám Khảo) để Cross-check 4 nhóm:
       VERIFIED_EQUAL / DATASET_SUPERIOR / CLOUD_SUPERIOR / REJECTED
  4. In log chi tiết ra màn hình + ghi file nháp kết quả.

Cách chạy:
  python src/reasoning_generation/pilot_run.py
"""

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
#  Cấu hình đường dẫn & biến môi trường
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from configs.paths import STRATIFIED_CSV, DATA_REASONING

load_dotenv(ROOT / ".env")

API_KEY   = os.getenv("DASHSCOPE_API_KEY_1")
# Dùng DashScope international public endpoint (không dùng MaaS endpoint riêng vì không hỗ trợ qwen3.7-plus)
BASE_URL  = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MODEL     = "qwen3.7-plus"      # Model Qwen mới nhất, giá tốt nhất
N_SAMPLE  = 3                   # Số dòng chạy thử
OUTPUT_LOG = DATA_REASONING / "pilot_run_log.json"

if not API_KEY or not BASE_URL:
    print("[FATAL] Không tìm thấy DASHSCOPE_API_KEY_1 hoặc DASHSCOPE_BASE_URL trong .env")
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
1. Suy luận kỹ lưỡng trong thẻ <think>: Phân tích câu hỏi, vận dụng kiến thức ngành thời trang, nguyên tắc phối đồ, chất liệu và xu hướng. Suy luận HOÀN TOÀN TỰ DO, không bị ảnh hưởng bởi bất kỳ câu trả lời có sẵn nào.
2. Trả lời cuối cùng bằng tiếng Việt sau thẻ </think>: Rõ ràng, chuyên nghiệp, thực tế và có chiều sâu.

Định dạng bắt buộc:
<think>
[Quá trình suy luận chi tiết tại đây]
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
#  Hàm gọi API
# --------------------------------------------------------------------------- #

def call_api(messages: list, max_tokens: int = 4096, temperature: float = 0.7,
             timeout: int = 240, max_retries: int = 2) -> dict:
    """
    Gọi API DashScope với định dạng OpenAI-compatible.
    Trả về dict: {"thinking": str, "answer": str, "raw_content": str, "usage": dict}
    qwen3.7-plus là reasoning model nặng — cần timeout >= 240s.
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=HEADERS,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            break  # thành công, thoát vòng lặp retry
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                wait = 5 * attempt
                print(f"  ⚠️  Attempt {attempt} failed ({e}). Retry sau {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise last_err

    data = resp.json()

    message = data["choices"][0]["message"]
    content = message.get("content", "") or ""
    usage   = data.get("usage", {})

    # qwen3.7-plus trả reasoning_content trong field RIÊNG (không inline <think> tags)
    thinking = message.get("reasoning_content", "") or ""

    # Fallback: nếu model vẫn trả inline <think> tags trong content
    if not thinking and "<think>" in content and "</think>" in content:
        think_start = content.index("<think>") + len("<think>")
        think_end   = content.index("</think>")
        thinking    = content[think_start:think_end].strip()
        content     = content[think_end + len("</think>"):].strip()

    answer = content.strip()

    return {
        "thinking": thinking,
        "answer": answer,
        "raw_content": content,
        "usage": usage,
    }


def call_judge(question: str, a_dataset: str, thinking_cloud: str, a_cloud: str) -> dict:
    """Gọi API ở vai trò Giám Khảo, trả về dict JSON đã parse."""
    user_msg = build_judge_user_message(question, a_dataset, thinking_cloud, a_cloud)
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]
    result = call_api(messages, max_tokens=1024, temperature=0.3)
    raw_json = result["answer"].strip()

    # Loại bỏ ```json ... ``` nếu model có bọc markdown
    if raw_json.startswith("```"):
        raw_json = "\n".join(raw_json.split("\n")[1:-1])

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        parsed = {"category": "PARSE_ERROR", "fact_check_notes": raw_json}

    parsed["_judge_usage"] = result["usage"]
    return parsed


# --------------------------------------------------------------------------- #
#  Main — Pilot Run
# --------------------------------------------------------------------------- #

def main():
    print("=" * 70)
    print(f"  PILOT RUN — Giai đoạn 5: Sinh Reasoning & Cross-Check")
    print(f"  Model : {MODEL}")
    print(f"  Sample: {N_SAMPLE} dòng đầu tiên từ stratified_1488.csv")
    print("=" * 70)

    # 1. Đọc dữ liệu
    df = pd.read_csv(STRATIFIED_CSV).head(N_SAMPLE)
    print(f"\n[INFO] Đã load {len(df)} dòng từ {STRATIFIED_CSV.name}\n")

    results = []
    total_input_tokens  = 0
    total_output_tokens = 0

    for idx, row in df.iterrows():
        question   = str(row["translated_input"]).strip()
        a_dataset  = str(row["translated_output"]).strip()
        tags       = str(row.get("Tags", "N/A"))
        batch_id   = row.get("batch_id", "N/A")
        row_id     = row.get("ID", idx)

        print(f"\n{'─' * 70}")
        print(f"  [Dòng {idx + 1}/{N_SAMPLE}] ID={row_id} | Tags: {tags} | Batch: {batch_id}")
        print(f"{'─' * 70}")
        print(f"  Q : {question[:120]}{'...' if len(question) > 120 else ''}")
        print(f"  A_Dataset : {a_dataset[:100]}{'...' if len(a_dataset) > 100 else ''}")

        # ── Bước 1: Sinh Reasoning & A_Cloud ──────────────────────────────
        print(f"\n  [Bước 1] Gọi {MODEL} sinh Reasoning + A_Cloud...", flush=True)
        try:
            gen_result = call_api(
                messages=[
                    {"role": "system", "content": REASONING_SYSTEM},
                    {"role": "user",   "content": question},
                ],
                max_tokens=2048,
                temperature=0.7,
            )
            thinking_cloud = gen_result["thinking"]
            a_cloud        = gen_result["answer"]
            usage_gen      = gen_result["usage"]

            tok_in  = usage_gen.get("prompt_tokens", 0)
            tok_out = usage_gen.get("completion_tokens", 0)
            total_input_tokens  += tok_in
            total_output_tokens += tok_out

            print(f"  ✅ Sinh xong | Tokens: {tok_in} in / {tok_out} out")
            print(f"\n  --- Thinking_Cloud (200 ký tự đầu) ---")
            print(f"  {thinking_cloud[:200]}{'...' if len(thinking_cloud) > 200 else ''}")
            print(f"\n  --- A_Cloud (150 ký tự đầu) ---")
            print(f"  {a_cloud[:150]}{'...' if len(a_cloud) > 150 else ''}")

        except Exception as e:
            print(f"  ❌ LỖI khi sinh reasoning: {e}")
            thinking_cloud = ""
            a_cloud        = f"ERROR: {e}"
            usage_gen      = {}

        time.sleep(1)  # Tránh rate-limit

        # ── Bước 2: Cross-Check (Giám Khảo) ───────────────────────────────
        print(f"\n  [Bước 2] Gọi Giám Khảo Cross-check...", flush=True)
        try:
            verdict = call_judge(question, a_dataset, thinking_cloud, a_cloud)
            tok_j_in  = verdict.get("_judge_usage", {}).get("prompt_tokens", 0)
            tok_j_out = verdict.get("_judge_usage", {}).get("completion_tokens", 0)
            total_input_tokens  += tok_j_in
            total_output_tokens += tok_j_out

            category = verdict.get("category", "UNKNOWN")
            notes    = verdict.get("fact_check_notes", "")

            emoji_map = {
                "VERIFIED_EQUAL":    "✅",
                "DATASET_SUPERIOR":  "📌",
                "CLOUD_SUPERIOR":    "🔄",
                "REJECTED":          "🗑️",
            }
            print(f"\n  {emoji_map.get(category, '❓')} VERDICT: {category}")
            print(f"  Notes: {notes[:300]}{'...' if len(notes) > 300 else ''}")
            print(f"  Tokens Giám Khảo: {tok_j_in} in / {tok_j_out} out")

        except Exception as e:
            print(f"  ❌ LỖI khi cross-check: {e}")
            verdict  = {"category": "ERROR", "fact_check_notes": str(e)}
            category = "ERROR"
            notes    = str(e)

        # ── Ghi kết quả ───────────────────────────────────────────────────
        results.append({
            "row_index":      idx,
            "id":             row_id,
            "tags":           tags,
            "batch_id":       str(batch_id),
            "question":       question,
            "a_dataset":      a_dataset,
            "thinking_cloud": thinking_cloud,
            "a_cloud":        a_cloud,
            "verdict":        verdict,
            "usage_gen":      usage_gen,
        })

        time.sleep(2)  # Nghỉ giữa các dòng

    # ── Tổng kết ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  📊 TỔNG KẾT PILOT RUN")
    print(f"{'=' * 70}")

    category_counts = {}
    for r in results:
        cat = r["verdict"].get("category", "UNKNOWN")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for cat, cnt in category_counts.items():
        emoji_map = {
            "VERIFIED_EQUAL":    "✅",
            "DATASET_SUPERIOR":  "📌",
            "CLOUD_SUPERIOR":    "🔄",
            "REJECTED":          "🗑️",
        }
        print(f"  {emoji_map.get(cat, '❓')} {cat}: {cnt} dòng")

    # Ước tính chi phí (qwen3.7-plus: $0.4/1M input, $1.6/1M output)
    cost_in  = (total_input_tokens  / 1_000_000) * 0.4
    cost_out = (total_output_tokens / 1_000_000) * 1.6
    total_cost = cost_in + cost_out
    print(f"\n  💰 Tổng Tokens: {total_input_tokens:,} input / {total_output_tokens:,} output")
    print(f"  💵 Chi phí ước tính: ${total_cost:.6f} USD")
    print(f"     (Input: ${cost_in:.6f} | Output: ${cost_out:.6f})")
    print(f"\n  📦 Ước tính chi phí cho 1488 dòng (x{1488 // N_SAMPLE} lần): ~${total_cost * (1488 / N_SAMPLE):.4f} USD")

    # Ghi log JSON
    OUTPUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ Đã ghi kết quả chi tiết vào: {OUTPUT_LOG}")
    print("=" * 70)


if __name__ == "__main__":
    main()
