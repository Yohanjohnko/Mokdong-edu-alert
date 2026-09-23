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

# 이미 알림을 보낸 글의 링크를 기록해두는 파일 — 중복 알림 방지용
SENT_FILE = "sent_links.txt"


def load_sent_links():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_links(links):
    if not links:
        return
    with open(SENT_FILE, "a", encoding="utf-8") as f:
        for link in links:
            f.write(link + "\n")


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
너는 목동 지역 영어유치원(영유) "2027학년도 신입 모집" 소식만 정확히 걸러내는 AI 에이전트다.

[전제]
- 오늘 날짜: 2026년 9월 기준
- 대상 아이: 2027년에 만 5세가 되는 아이 (즉 2027학년도 정규반/신입 모집 대상)
- 이 에이전트의 목적은 딱 하나: "2027학년도 입학설명회/신입 원아 모집 공고"를 놓치지 않는 것

수집된 아래 포스팅을 분석해서 판단해라.

[수집 정보]
제목: {title}
내용: {description}
링크: {link}

[반드시 SKIP 처리할 경우 — 아래 중 하나라도 해당되면 무조건 "SKIP"]
- 학원/부동산 광고, 키워드 낚시글, 본문과 무관한 글
- 2025학년도 이전이거나 이미 종료된 과거 모집 공고 (글에 25년, 작년, 지난, 종료 등의 표현이 있거나 문맥상 과거 시점으로 보이는 경우)
- 초1, 예비초1, 초등 입학, 초등 준비반 등 초등학교 관련 내용 (이 아이는 아직 유치원 대상이라 전혀 무관함)
- 단순 유치원 후기, 커리큘럼 소개, 학부모 일상 후기 등 "모집/설명회 공고"가 아닌 글
- 2027학년도 여부가 불분명하고 애매한 경우

[유용한 공고로 인정할 경우]
아래 3줄 요약 양식으로만 깔끔하게 작성해서 출력해라. 다른 설명은 붙이지 마라.
- 1줄: [유치원명 / 대상 연령]
- 2줄: [일정 및 주요 내용]
- 3줄: [신청 및 접수 방법]

[응답 지침]
판단이 애매하면 무조건 "SKIP"으로 처리해라. 확실한 경우만 통과시켜라.
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
    already_sent = load_sent_links()
    newly_sent = []

    for query in SEARCH_QUERIES:
        candidates = fetch_naver_items(query, "blog") + fetch_naver_items(query, "cafearticle")

        for item in candidates:
            link = item.get("link", "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            if link in already_sent:
                continue  # 이미 이전에 알림을 보낸 글이면 건너뜀 (중복 방지)

            title = clean_html(item.get("title", ""))
            desc = clean_html(item.get("description", ""))
            if not title:
                continue

            ai_summary = analyze_post_with_ai(title, desc, link)
            if ai_summary and "SKIP" not in ai_summary:
                msg = f"🤖 **[목동 영유 실시간 포착 알림]**\n\n**원문:** [{title}]({link})\n\n💡 **AI 3줄 요약:**\n{ai_summary}"
                send_telegram(msg)
                sent_count += 1
                newly_sent.append(link)

    save_sent_links(newly_sent)
    print(f"모니터링 완료. 텔레그램 알림 전송: {sent_count}건")
