import requests
import json
import pandas as pd

df = pd.read_csv('data/processed/distilled_1500_pre_audit.csv')
row = df.iloc[0]

user_prompt = (
    "Bạn là một Chuyên gia Ngôn ngữ học và Tư vấn thời trang. Kiểm tra xem bản dịch tiếng Việt có lỗi dịch thuật không.\n"
    "1. Lỗi giữ nguyên tiếng Anh không cần thiết.\n"
    "2. Lỗi sai nghĩa (Word-by-word).\n"
    "3. Lỗi xưng hô lộn xộn.\n\n"
    f"--- GỐC (EN) ---\nQ: {row['original_input']}\nA: {row['original_output']}\n\n"
    f"--- DỊCH (VI) ---\nQ: {row['translated_input']}\nA: {row['translated_output']}\n\n"
    "Chỉ trả về 'ERROR' hoặc 'OK':"
)

payload = {
    "contents": [{"parts": [{"text": user_prompt}]}],
    "generationConfig": {"temperature": 0.1}
}

import os
from dotenv import load_dotenv
load_dotenv()

KEY = os.getenv("GEMMA_API_KEY_1", "")
url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={KEY}'
response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=60)
print(response.status_code)
try:
    print(response.text)
except:
    pass
