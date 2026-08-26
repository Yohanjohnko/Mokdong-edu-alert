import os
import requests
import xml.etree.ElementTree as ET
from google import genai

# 환경 변수 로드 (기존 Secrets 키 자동 사용)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

# 트렌드/정보성 이슈 RSS 수집 (정부 지원금, 환급금, 정책 관련)
RSS_URL = "https://news.google.com/rss/search?q=%EC%A0%95%EB%B6%80%EC%A0%9C%EB%8F%84+%EC%B2%AD%EC%95%BD+%ED%99%98%EA%B8%89%EA%B8%88&hl=ko&gl=KR&ceid=KR:ko"

def get_latest_news():
    try:
        res = requests.get(RSS_URL)
        root = ET.fromstring(res.text)
        items = root.findall('./channel/item')
        if items:
            title = items[0].find('title').text
            link = items[0].find('link').text
            return title, link
    except Exception as e:
        print(f"RSS 수집 오류: {e}")
    return None, None

def generate_blog_post(topic_title):
    prompt = f"""
너는 네이버 블로그 검색 상위 노출 전문 카피라이터다.
다음 최신 주제를 바탕으로 블로그 포스팅 원고 초안을 작성해라.

주제: {topic_title}

[작성 가이드라인]:
1. 제목: 클릭율이 높은 제목 추천 3개
2. 서론: 독자의 공감을 이끄는 도입부 (2~3문장)
3. 본문: 소제목 2~3개로 구별하여 핵심 내용 상세 설명 (가독성 좋게 문단 구분)
4. 결론: 한 줄 요약 및 댓글 유도 질문
5. 추천 태그: 연관 해시태그 5개 (#포함)

바로 복사해서 블로그에 붙여넣을 수 있도록 깔끔한 마크다운 형식으로 작성해라.
"""
    # 구글 API 최신 정식 모델(gemini-3.6-flash) 적용
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )
    return response.text

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

if __name__ == "__main__":
    title, link = get_latest_news()
    if title:
        draft = generate_blog_post(title)
        msg = f"📝 **[오늘의 블로그 포스팅 초안]**\n\n**출처 뉴스:** {title}\n\n{draft}"
        send_telegram(msg)
        print("블로그 초안 텔레그램 전송 완료!")
    else:
        print("수집된 뉴스가 없습니다.")
