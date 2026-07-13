# -*- coding: utf-8 -*-
"""
repair_parse_errors.py — Tự động sửa chữa 4 dòng PARSE_ERROR trong file CSV cuối cùng
===================================================================================
Các dòng ID: 9298, 7741, 7803, 4078 bị phân loại nhầm là PARSE_ERROR do chuỗi JSON trả về
từ Giám khảo bị lỗi định dạng (ví dụ: xuống dòng không escape). Tuy nhiên, nội dung thực tế
đều là CLOUD_SUPERIOR.
Script này sẽ sửa đổi trực tiếp file CSV và log JSON để chuyển chúng thành CLOUD_SUPERIOR
và cập nhật final_response tương ứng sang A_Cloud.
"""

import json
import re
import sys
from pathlib import Path
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

ROOT = Path(__file__).parent.parent.parent
LOG_PATH = ROOT / "data" / "reasoning_generation" / "reasoning_generation_log.json"
CSV_PATH = ROOT / "data" / "final" / "final_distilled_reasoning_1488.csv"

def repair():
    print("=" * 80)
    print("Bắt đầu sửa chữa 4 dòng PARSE_ERROR thành CLOUD_SUPERIOR...")
    
    # 1. Sửa trong log JSON
    if LOG_PATH.exists():
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            log_data = json.load(f)
            
        modified_log = False
        for item in log_data:
            r_id = item["id"]
            if r_id in [9298, 7741, 7803, 4078]:
                print(f"-> Sửa JSON Log cho ID={r_id}")
                # Parse thủ công từ text nếu có thể
                raw_answer = item["verdict"].get("fact_check_notes", "")
                
                # Cập nhật thông tin verdict
                item["verdict"]["category"] = "CLOUD_SUPERIOR"
                # Làm sạch ghi chú
                clean_notes = raw_answer.replace('{"category": "CLOUD_SUPERIOR", "fact_check_notes": "', '')
                clean_notes = clean_notes.replace('{"category":"CLOUD_SUPERIOR","fact_check_notes":"', '')
                clean_notes = clean_notes.rstrip('"}').strip()
                item["verdict"]["fact_check_notes"] = clean_notes
                modified_log = True
                
        if modified_log:
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            print("✅ Đã cập nhật reasoning_generation_log.json thành công!")
            
    # 2. Sửa trong CSV
    if CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH)
        
        # Để cập nhật chính xác, ta sẽ lấy thông tin a_cloud và thinking_cloud từ log JSON
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            log_data = json.load(f)
        log_dict = {item["id"]: item for item in log_data}
        
        for idx, row in df.iterrows():
            r_id = int(row["ID"])
            if r_id in [9298, 7741, 7803, 4078]:
                print(f"-> Sửa CSV cho ID={r_id}")
                log_item = log_dict[r_id]
                thinking = log_item["thinking_cloud"]
                a_cloud = log_item["a_cloud"]
                
                # Cập nhật category
                df.at[idx, "category"] = "CLOUD_SUPERIOR"
                # Cập nhật fact_check_notes
                df.at[idx, "fact_check_notes"] = log_item["verdict"]["fact_check_notes"]
                # Cập nhật response dùng a_cloud thay vì a_dataset
                df.at[idx, "final_response"] = f"<think>\n{thinking}\n</think>\n{a_cloud}"
                
        df.to_csv(CSV_PATH, index=False)
        print("✅ Đã cập nhật final_distilled_reasoning_1488.csv thành công!")
        
    print("=" * 80)
    print("HOÀN THÀNH SỬA CHỮA!")
    print("=" * 80)

if __name__ == "__main__":
    repair()
