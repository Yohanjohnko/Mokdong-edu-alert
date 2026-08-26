import os
import requests
import google.generativeai as genai

# 1. 환경변수 검증
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not all([GEMINI_API_KEY, TELEGRAM_TOKEN, CHAT_ID]):
    raise ValueError("필수 환경변수(GEMINI_API_KEY, TELEGRAM_TOKEN, CHAT_ID)가 깃허브 Secrets에 세팅되어 있지 않습니다.")

# 2. Gemini API 설정 및 원고 생성
genai.configure(api_key=GEMINI_API_KEY)

# 최신 활성 모델 목록 (gemini-3.6-flash 최우선)
models_to_try = [
    "gemini-3.6-flash",
    "gemini-2.5-flash"
]

prompt = """
네이버 블로그용 원고 초안을 작성해 줘.
독자가 읽기 쉽도록 친근한 어조로 작성하고, 특수문자 사용을 최소화해 줘.
"""

draft_text = None

for model_name in models_to_try:
    try:
        print(f"[{model_name}] 모델로 초안 생성 시도 중...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        if response and response.text:
            draft_text = response.text
            print(f"성공된 모델: {model_name}")
            break
    except Exception as e:
        print(f"[{model_name}] 서버 응답 대기/실패 ({e}). 다음 백업 모델로 재시도합니다.")

if not draft_text:
    raise RuntimeError("모든 Gemini 모델 호출에 실패했습니다.")

# 3. 텔레그램 전송
url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": draft_text
}

telegram_response = requests.post(url, json=payload)
telegram_response.raise_for_status()

print("블로그 초안 텔레그램 전송 완료!")
