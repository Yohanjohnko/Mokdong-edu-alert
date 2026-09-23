import os
import re
import requests
from google import genai

# 환경 변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

client = genai.Client(api_key=GEMINI_API_KEY)

# 수집 대상 자동 검색 키워드
SEARCH_QUERIES = [
    "목동 영유 설명회",
    "목동 폴리 모집",
    "목동 라이즈 설명회",
    "목동 프랜시스파커 입학",
    "목동 SLP 모집",
    "목동 영어유치원",
]


def clean_html(text):
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.replace("&quot;", '"').replace("&amp;", '&').replace("&lt;", '<').replace("&gt;", '>')


def fetch_naver_items(query, section):
    """section: 'blog' 또는 'cafearticle' — 네이버 블로그/카페글 검색
    2026년 7월 검색 API가 NAVER API HUB(네이버 클라우드 플랫폼)로 이전되어
    엔드포인트와 인증 헤더가 예전 openapi.naver.com 방식과 달라졌다."""
    url = f"https://naverapihub.apigw.ntruss.com/search/v1/{section}"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": 3, "sort": "date", "format": "json"}  # 최신순 3개
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("items", [])
    except Exception as e:
        print(f"[{query}/{section}] 네이버 검색 에러: {e}")
        return []


def analyze_post_with_ai(title, description, link):
    prompt = f"""
너는 목동 지역 영어유치원(영유) 입학/설명회 소식을 모니터링하는 AI 에이전트다.

수집된 아래 포스팅을 분석하여 단순 학원 광고, 부동산 홍보, 키워드 낚시글은 제외하고,
실제 영어유치원(폴리, 라이즈, 프랜시스파커, SLP, 월넛, PSA 등)의 설명회, 신규 원아 모집 공고, 레벨테스트 일정 또는 핵심 유용한 정보인지 판단해라.

[수집 정보]
제목: {title}
내용: {description}
링크: {link}

[응답 지침]
1. 광고/부동산/무관한 정보인 경우: 오직 "SKIP" 단어 하나만 출력해라.
2. 유용한 입학/설명회 공고인 경우:
- 1줄: [유치원명 / 대상 연령]
- 2줄: [일정 및 주요 내용]
- 3줄: [신청 및 접수 방법]
위 3줄 요약 양식으로만 깔끔하게 작성해서 출력해라.
"""
    candidate_models = ['gemini-3.6-flash', 'gemini-3.5-flash-lite']
    for model_name in candidate_models:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            result = response.text.strip()
            print(f"[{model_name}] 성공적으로 감지 완료")
            return result
        except Exception as e:
            print(f"[{model_name}] 호출 실패 ({e}). 백업 모델로 재시도합니다.")
    print("모든 백업 Gemini 모델 응답에 실패했습니다.")
    return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"텔레그램 발송 예외 발생: {e}")


if __name__ == "__main__":
    print("목동 영유 자동 알림 에이전트 가동 시작... (네이버 블로그/카페 검색 기반)")
    sent_count = 0
    seen_links = set()

    for query in SEARCH_QUERIES:
        candidates = fetch_naver_items(query, "blog") + fetch_naver_items(query, "cafearticle")

        for item in candidates:
            link = item.get("link", "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            title = clean_html(item.get("title", ""))
            desc = clean_html(item.get("description", ""))
            if not title:
                continue

            ai_summary = analyze_post_with_ai(title, desc, link)
            if ai_summary and "SKIP" not in ai_summary:
                msg = f"🤖 **[목동 영유 실시간 포착 알림]**\n\n**원문:** [{title}]({link})\n\n💡 **AI 3줄 요약:**\n{ai_summary}"
                send_telegram(msg)
                sent_count += 1

    print(f"모니터링 완료. 텔레그램 알림 전송: {sent_count}건")
