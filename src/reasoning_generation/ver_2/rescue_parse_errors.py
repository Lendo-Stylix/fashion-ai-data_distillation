# -*- coding: utf-8 -*-
"""
rescue_parse_errors.py — Giải cứu các dòng PARSE_ERROR
======================================================
"""

import json
import sys
import re
import time
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
from configs.paths import STRATIFIED_CSV, DATA_REASONING, DATA_FINAL

load_dotenv(ROOT / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
from src.reasoning_generation.ver_2.run_reasoning_pipeline_openrouter import (
    call_api, step3_reverse_prompt, API_KEYS, OUTPUT_LOG, FINAL_OUTPUT_CSV, JUDGE_SYSTEM
)

def rescue_row(item, api_key):
    row_id = item["id"]
    verdict = item.get("verdict", {})
    category = verdict.get("category", "PARSE_ERROR")
    
    if category != "PARSE_ERROR":
        return item, False

    raw_response = verdict.get("raw_judge_response") or verdict.get("fact_check_notes") or ""
    
    # Thử quét bằng regex trước
    cat_match = re.search(r'"category"\s*:\s*"([A-Z_]+)"', raw_response)
    note_match = re.search(r'"fact_check_notes"\s*:\s*"([^"]+)"', raw_response)
    
    new_cat = "PARSE_ERROR"
    if cat_match and cat_match.group(1) in ("VERIFIED_EQUAL", "CLOUD_SUPERIOR", "DATASET_SUPERIOR", "REJECTED"):
        new_cat = cat_match.group(1)
        notes = note_match.group(1) if note_match else raw_response[:300]
        print(f"  [Regex Success] ID={row_id} → {new_cat}")
    else:
        # Nếu regex không ra, gọi lại API Judge với temp=0.1
        print(f"  [API Re-Judge] ID={row_id} calling API...")
        try:
            user_msg = f"""Hãy so sánh 2 câu trả lời thời trang sau:

===== CÂU HỎI =====
{item["question"]}

===== A_Dataset (câu trả lời gốc) =====
{item["question"]}

===== A_Cloud (câu trả lời AI) =====
{item.get("a_cloud", "")}

Thực hiện so sánh theo 2 tiêu chí. Trả về JSON thuần."""

            res = call_api(
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=2500,
                temperature=0.1,
                api_key=api_key
            )
            raw = res["content"]
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw.replace("```json", "").replace("```", "")
            
            try:
                parsed = json.loads(raw)
                new_cat = parsed.get("category", "PARSE_ERROR")
                notes = parsed.get("fact_check_notes", raw[:300])
            except Exception:
                # Thử quét regex trên phản hồi mới
                cat_m = re.search(r'"category"\s*:\s*"([A-Z_]+)"', raw)
                new_cat = cat_m.group(1) if cat_m else "PARSE_ERROR"
                notes = raw[:300]
            
            print(f"  [API Re-Judge Success] ID={row_id} → {new_cat}")
            time.sleep(3)
        except Exception as e:
            print(f"  ❌ [API Re-Judge Failed] ID={row_id}: {e}")
            return item, False

    if new_cat == "PARSE_ERROR":
        # Không giải cứu được, giữ nguyên
        return item, False

    # Cập nhật kết quả phân loại
    item["verdict"]["category"] = new_cat
    item["verdict"]["fact_check_notes"] = notes
    
    # Xác định nguồn câu trả lời mới
    old_source = item.get("a_final_source", "A_Dataset")
    if new_cat == "REJECTED":
        item["a_final"] = None
        item["a_final_source"] = "REJECTED"
        item["thinking_reverse"] = None
        item["final_response"] = None
        print(f"  [Update] ID={row_id} → REJECTED")
    else:
        new_source = "A_Cloud" if new_cat in ("VERIFIED_EQUAL", "CLOUD_SUPERIOR") else "A_Dataset"
        item["a_final_source"] = new_source
        
        if new_source == "A_Cloud":
            item["a_final"] = item["a_cloud"]
        else:
            item["a_final"] = item["a_dataset"]
            
        # Nếu nguồn đổi sang A_Cloud, bắt buộc phải sinh lại thinking tương thích
        if new_source == "A_Cloud" and old_source != "A_Cloud":
            print(f"  [Regen Thinking] ID={row_id} source changed to A_Cloud. Regenerating thinking...")
            try:
                s3 = step3_reverse_prompt(item["question"], item["a_final"], api_key)
                item["thinking_reverse"] = s3["content"]
                item["usage_step3"] = s3["usage"]
                item["final_response"] = f"<think>\n{s3['content']}\n</think>\n{item['a_final']}"
                print(f"  [Regen Thinking Success] ID={row_id} Thinking={len(s3['content'])}c")
                time.sleep(3)
            except Exception as e:
                print(f"  ❌ [Regen Thinking Failed] ID={row_id}: {e}")
                # Hoàn tác nguồn về cũ để đảm bảo an toàn
                item["a_final_source"] = old_source
                item["a_final"] = item["a_dataset"]
                return item, False
        else:
            # Nếu giữ nguyên Dataset hoặc không đổi nguồn sang Cloud, cập nhật final response bình thường
            if new_source == "A_Dataset":
                item["final_response"] = f"<think>\n{item.get('thinking_reverse') or ''}\n</think>\n{item['a_final']}"

    return item, True

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    if not OUTPUT_LOG.exists():
        print(f"Không tìm thấy file log: {OUTPUT_LOG}")
        return
        
    with open(OUTPUT_LOG, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Tổng số dòng trong log: {len(data)}")
    parse_errors = [item for item in data if item.get("verdict", {}).get("category") == "PARSE_ERROR"]
    print(f"Số dòng bị PARSE_ERROR cần giải cứu: {len(parse_errors)}")
    
    if not parse_errors:
        print("Không có dòng PARSE_ERROR nào. Kết thúc.")
        return
        
    api_key = API_KEYS[0]
    rescued_count = 0
    
    for i, item in enumerate(data):
        if item.get("verdict", {}).get("category") == "PARSE_ERROR":
            updated_item, success = rescue_row(item, api_key)
            if success:
                data[i] = updated_item
                rescued_count += 1
                
                # Lưu checkpoint lũy tiến
                with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
                # Cập nhật tệp CSV
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
                
    print(f"Hoàn tất! Đã giải cứu thành công {rescued_count}/{len(parse_errors)} dòng PARSE_ERROR.")

if __name__ == "__main__":
    main()
