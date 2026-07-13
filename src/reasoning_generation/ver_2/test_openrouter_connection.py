# -*- coding: utf-8 -*-
"""
test_openrouter_connection.py — Kiểm tra kết nối OpenRouter API
================================================================
Script này giúp kiểm tra xem API key của bạn có hoạt động không
và model tencent/hy3:free có sẵn sàng không.

Cách chạy:
  python src/reasoning_generation/ver_2/test_openrouter_connection.py
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "tencent/hy3:free"

if not API_KEY:
    print("❌ [LỖI] Không tìm thấy OPENROUTER_API_KEY trong .env")
    print("\n[HƯỚNG DẪN CẤU HÌNH]:")
    print("1. Tạo file .env trong thư mục gốc /workspace/.env")
    print("2. Thêm dòng sau vào file .env:")
    print("   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx")
    print("\n3. Lấy API Key từ: https://openrouter.ai/keys")
    sys.exit(1)

print("=" * 70)
print("  KIỂM TRA KẾT NỐI OPENROUTER API")
print("=" * 70)
print(f"\n✅ Đã tìm thấy API Key (bắt đầu bằng: {API_KEY[:15]}...)")
print(f"📡 Endpoint: {BASE_URL}")
print(f"🤖 Model: {MODEL}")

# Test câu hỏi đơn giản
test_question = "How many r's are in the word 'strawberry'?"

print(f"\n🔍 Đang gửi câu hỏi test: '{test_question}'")
print("-" * 70)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/your-repo",
    "X-Title": "OpenRouter Connection Test",
}

payload = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": test_question}
    ],
    "reasoning": {"enabled": True},
    "max_tokens": 1024,
    "temperature": 0.7,
    "stream": False,
}

try:
    print("\n⏳ Đang gọi API...")
    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )

    print(f"\n📥 Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        # Hiển thị thông tin response
        print("\n✅ API Call Thành Công!")
        print("-" * 70)

        # Thông tin model thực tế được sử dụng
        actual_model = data.get("model", MODEL)
        print(f"🤖 Model thực tế: {actual_model}")

        # Usage stats
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        print(f"\n📊 Token Usage:")
        print(f"   - Prompt tokens: {prompt_tokens}")
        print(f"   - Completion tokens: {completion_tokens}")
        print(f"   - Total tokens: {total_tokens}")

        # Extract response
        message = data['choices'][0]['message']
        content = message.get('content', '')
        reasoning_details = message.get('reasoning_details', [])

        print("\n💭 Reasoning Details:")
        if reasoning_details:
            for i, detail in enumerate(reasoning_details, 1):
                if isinstance(detail, dict) and 'text' in detail:
                    text = detail['text']
                    # Hiển thị 300 ký tự đầu
                    preview = text[:300] + "..." if len(text) > 300 else text
                    print(f"   Part {i}: {preview}")
        else:
            print("   (Không có reasoning_details trong response)")

        print("\n💬 Content (Câu trả lời):")
        content_preview = content[:500] + "..." if len(content) > 500 else content
        print(f"   {content_preview}")

        print("\n" + "=" * 70)
        print("✅ KẾT LUẬN: API Key hợp lệ và model hoạt động tốt!")
        print("=" * 70)

    elif response.status_code == 401:
        print("\n❌ LỖI XÁC THỰC (401 Unauthorized)")
        print("   Nguyên nhân: API Key không hợp lệ hoặc đã hết hạn")

    elif response.status_code == 429:
        print("\n⚠️  RATE LIMIT (429 Too Many Requests)")

    elif response.status_code == 403:
        print("\n❌ FORBIDDEN (403)")
        error_data = response.json()
        print(f"   Chi tiết: {error_data}")

    else:
        print(f"\n❌ LỖI KHÔNG XÁC ĐỊNH ({response.status_code})")
        print(f"   Response: {response.text[:500]}")

except requests.exceptions.Timeout:
    print("\n❌ TIMEOUT: API call vượt quá thời gian cho phép (120s)")

except requests.exceptions.ConnectionError as e:
    print(f"\n❌ LỖI KẾT NỐI: {e}")

except Exception as e:
    print(f"\n❌ LỖI KHÔNG XÁC ĐỊNH: {e}")
    import traceback
    traceback.print_exc()
