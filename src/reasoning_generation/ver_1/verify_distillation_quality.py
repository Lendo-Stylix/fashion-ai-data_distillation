# -*- coding: utf-8 -*-
"""
verify_distillation_quality.py — Kiểm định chất lượng dữ liệu sau chưng cất (Giai đoạn 5)
===================================================================================
Script này thực hiện kiểm tra chất lượng tự động và lập thống kê chi tiết trên:
  1. File log thô: data/reasoning_generation/reasoning_generation_log.json
  2. File kết quả cuối cùng: data/final/final_distilled_reasoning_1488.csv
"""

import json
import re
import sys
from pathlib import Path
import pandas as pd

# Đảm bảo in utf-8 trên console
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

ROOT = Path(__file__).parent.parent.parent
LOG_PATH = ROOT / "data" / "reasoning_generation" / "reasoning_generation_log.json"
CSV_PATH = ROOT / "data" / "final" / "final_distilled_reasoning_1488.csv"

def run_quality_check():
    print("=" * 80)
    # 1. Đọc và phân tích file log JSON
    print(f"[1] Đọc file log chi tiết từ: {LOG_PATH}")
    if not LOG_PATH.exists():
        print(f"[LỖI] File log không tồn tại tại {LOG_PATH}")
        return
        
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        log_data = json.load(f)
        
    total_log_rows = len(log_data)
    print(f"-> Tổng số dòng trong log: {total_log_rows}")
    
    # Thống kê phân phối verdict
    verdicts = []
    model_gen_counts = {}
    model_judge_counts = {}
    empty_thinking_count = 0
    empty_answer_count = 0
    parse_errors_details = []
    
    for item in log_data:
        verdict_obj = item.get("verdict", {})
        cat = verdict_obj.get("category", "UNKNOWN")
        verdicts.append(cat)
        
        # Thống kê model sinh
        m_gen = item.get("model_gen", "UNKNOWN")
        model_gen_counts[m_gen] = model_gen_counts.get(m_gen, 0) + 1
        
        # Thống kê model chấm
        m_judge = verdict_obj.get("_judge_model", "UNKNOWN")
        model_judge_counts[m_judge] = model_judge_counts.get(m_judge, 0) + 1
        
        # Kiểm tra rỗng
        thinking = item.get("thinking_cloud", "").strip()
        answer = item.get("a_cloud", "").strip()
        if not thinking:
            empty_thinking_count += 1
        if not answer:
            empty_answer_count += 1
            
        if cat == "PARSE_ERROR":
            parse_errors_details.append({
                "id": item["id"],
                "notes": verdict_obj.get("fact_check_notes", "")
            })
            
    df_verdict = pd.Series(verdicts)
    verdict_counts = df_verdict.value_counts()
    verdict_pct = df_verdict.value_counts(normalize=True) * 100
    
    print("\n[Thống kê phân phối Đánh giá từ Giám khảo (Verdicts)]")
    for cat in verdict_counts.index:
        print(f"  - {cat}: {verdict_counts[cat]} dòng ({verdict_pct[cat]:.2f}%)")
        
    print("\n[Thống kê sử dụng Model sinh Reasoning (Bước 1)]")
    for m, count in sorted(model_gen_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {m}: {count} dòng ({count/total_log_rows*100:.2f}%)")
        
    print("\n[Thống kê sử dụng Model Giám khảo (Bước 2)]")
    for m, count in sorted(model_judge_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {m}: {count} dòng ({count/total_log_rows*100:.2f}%)")
        
    print(f"\n[Kiểm tra lỗi dữ liệu trong log]")
    print(f"  - Số dòng trống phần Reasoning (thinking_cloud): {empty_thinking_count}")
    print(f"  - Số dòng trống phần Answer (a_cloud): {empty_answer_count}")
    print(f"  - Lỗi Parse JSON Giám khảo (PARSE_ERROR): {len(parse_errors_details)}")
    if parse_errors_details:
        for err in parse_errors_details[:5]:
            print(f"    * ID={err['id']}: {err['notes'][:100]}...")
            
    print("=" * 80)
    
    # 2. Đọc và phân tích file CSV kết quả cuối cùng
    print(f"[2] Đọc và kiểm định file CSV cuối cùng từ: {CSV_PATH}")
    if not CSV_PATH.exists():
        print(f"[LỖI] File CSV cuối cùng không tồn tại tại {CSV_PATH}")
        return
        
    df_final = pd.read_csv(CSV_PATH)
    total_csv_rows = len(df_final)
    print(f"-> Tổng số dòng trong file CSV cuối cùng: {total_csv_rows}")
    
    # Đếm số dòng bị REJECTED
    rejected_count = total_log_rows - total_csv_rows
    print(f"-> Số dòng bị REJECTED (đã loại bỏ khỏi CSV): {rejected_count} dòng")
    
    # Kiểm định định dạng cấu trúc <think>...</think>
    think_pattern = re.compile(r"^<think>\n.*?\n</think>\n.+$", re.DOTALL)
    format_errors = []
    
    for idx, row in df_final.iterrows():
        r_id = row["ID"]
        resp = str(row["final_response"])
        if not think_pattern.match(resp):
            format_errors.append(r_id)
            
    print(f"\n[Kiểm tra định dạng cấu trúc thẻ <think>...</think>]")
    if not format_errors:
        print("  ✅ HOÀN HẢO: 100% số dòng trong CSV đạt chuẩn định dạng <think>\n...\n</think>\n[Answer]")
    else:
        print(f"  ❌ LỖI ĐỊNH DẠNG: Có {len(format_errors)} dòng không đúng định dạng chuẩn:")
        for err_id in format_errors[:5]:
            print(f"    * ID={err_id}")
            
    # Thống kê độ dài text
    print("\n[Thống kê độ dài ký tự trong kết quả cuối cùng]")
    df_final["q_len"] = df_final["question"].str.len()
    df_final["resp_len"] = df_final["final_response"].str.len()
    
    print(f"  - Độ dài câu hỏi (Question): Min={df_final['q_len'].min()} | Max={df_final['q_len'].max()} | Avg={df_final['q_len'].mean():.1f} ký tự")
    print(f"  - Độ dài câu trả lời cuối cùng (Reasoning + Answer): Min={df_final['resp_len'].min()} | Max={df_final['resp_len'].max()} | Avg={df_final['resp_len'].mean():.1f} ký tự")
    
    # Kiểm tra giá trị Null/Nan trong CSV
    null_counts = df_final.isnull().sum()
    print(f"\n[Kiểm tra giá trị Null/Nan trong các cột CSV]")
    for col, n_count in null_counts.items():
        if col in ["q_len", "resp_len"]:
            continue
        print(f"  - Cột '{col}': {n_count} giá trị Null")
        
    print("=" * 80)
    print("   HOÀN THÀNH QUÁ TRÌNH KIỂM ĐỊNH CHẤT LƯỢNG")
    print("=" * 80)

if __name__ == "__main__":
    run_quality_check()
