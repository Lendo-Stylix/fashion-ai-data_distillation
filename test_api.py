# -*- coding: utf-8 -*-
import os, requests, time
from dotenv import load_dotenv

load_dotenv('.env')
key = os.getenv('DASHSCOPE_API_KEY_1')
url = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions'
headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

models_to_test = ['qwen3.7-plus', 'qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen3-235b-a22b', 'qwen2.5-72b-instruct']
for model in models_to_test:
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Hi, say OK only.'}],
        'max_tokens': 20,
        'stream': False
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        data = r.json()
        if r.status_code == 200:
            content = data['choices'][0]['message'].get('content', '')
            reasoning = data['choices'][0]['message'].get('reasoning_content', '')
            print(f'[OK] {model}: answer={content[:50]} | think_len={len(reasoning)}')
        else:
            err = data.get('error', {}).get('message', str(data))
            print(f'[ERR {r.status_code}] {model}: {err[:100]}')
    except Exception as e:
        print(f'[TIMEOUT/ERR] {model}: {e}')
    time.sleep(2)
