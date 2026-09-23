import os
import re
import requests
from google import genai

# 1. 환경변수 검증
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

if not all([GEMINI_API_KEY, TELEGRAM_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET]):
    raise ValueError("필수 환경변수가 깃허브 Secrets에 세팅되어 있지 않습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

# 화제성 파악용 카테고리 (실제 조회수 데이터는 API로 못 가져오므로,
# 최신 관련도 높은 기사들을 모아 AI가 그중 가장 화제성 있는 2개를 고르게 함)
NEWS_QUERIES = ["부동산", "재테크", "경제"]


def clean_html(text):
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.replace("&quot;", '"').replace("&amp;", '&').replace("&lt;", '<').replace("&gt;", '>')


def fetch_news(query, display=5):
    """NAVER API HUB 뉴스 검색 — sim(관련도) 정렬로 화제성 높은 기사 위주 수집"""
    url = "https://naverapihub.apigw.ntruss.com/search/v1/news"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "sort": "sim", "format": "json"}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("items", [])
    except Exception as e:
        print(f"[{query}] 뉴스 검색 에러: {e}")
        return []


# 2. 부동산/재테크/경제 최신 화제 기사 수집
candidates = []
seen_links = set()
for q in NEWS_QUERIES:
    for item in fetch_news(q):
        link = item.get("link", "")
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        candidates.append({
            "title": clean_html(item.get("title", "")),
            "desc": clean_html(item.get("description", "")),
            "link": link,
        })

if not candidates:
    raise RuntimeError("네이버 뉴스에서 후보 기사를 하나도 가져오지 못했습니다.")

listing = "\n".join(f"{i + 1}. {c['title']} - {c['desc']}" for i, c in enumerate(candidates))

# 3. Gemini에게 가장 화제성 있는 Top 2 주제를 고르고, 각각 블로그 초안 작성 요청
prompt = f"""
너는 네이버 블로그(부동산/재테크/경제 카테고리)를 운영하는 블로거를 돕는 AI 에이전트다.

아래는 최근 부동산, 재테크, 경제 관련 뉴스 기사 목록이다.

[기사 목록]
{listing}

[할 일]
1. 이 중에서 블로그 독자가 가장 관심을 가질 만한, 화제성 있는 주제 2개를 골라라.
2. 각 주제마다 네이버 블로그용 원고 초안을 작성해라.
   - 독자가 읽기 편하도록 친근한 어조, 자연스러운 문장으로 작성
   - 특수문자 사용은 최소화
   - 각 초안은 500자 내외

[출력 형식]
반드시 아래 형식을 정확히 지켜서 출력해라. 다른 설명이나 인사말은 붙이지 마라.

[주제1: 주제명]
(초안 내용)

[주제2: 주제명]
(초안 내용)
"""

candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
draft_text = None
for model_name in candidate_models:
    try:
        print(f"[{model_name}] 초안 생성 시도 중...")
        response = client.models.generate_content(model=model_name, contents=prompt)
        if response and response.text:
            draft_text = response.text
            print(f"성공된 모델: {model_name}")
            break
    except Exception as e:
        print(f"[{model_name}] 호출 실패 ({e}). 다음 백업 모델로 재시도합니다.")

if not draft_text:
    raise RuntimeError("모든 Gemini 모델 호출에 실패했습니다.")

# 4. 텔레그램 전송
url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
payload = {"chat_id": CHAT_ID, "text": draft_text}
telegram_response = requests.post(url, json=payload)
telegram_response.raise_for_status()
print("블로그 초안 텔레그램 전송 완료!")
