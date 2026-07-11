import requests
import json
import pandas as pd

df = pd.read_csv('data/processed/distilled_1500_pre_audit.csv')
row = df.iloc[0]

user_prompt = (
    "Bạn là chuyên gia. Trả về ERROR hoặc OK:\n"
    f"EN: {row['original_input']} {row['original_output']}\n"
    f"VI: {row['translated_input']} {row['translated_output']}\n"
)

payload = {'contents': [{'parts': [{'text': user_prompt}]}]}
import os
from dotenv import load_dotenv
load_dotenv()

KEY = os.getenv("GEMMA_API_KEY_1", "")
url = f'https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent?key={KEY}'
response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
print(response.status_code)
try:
    print(json.dumps(response.json(), indent=2))
except:
    pass
