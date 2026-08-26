import os
import json
import ssl
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from google import genai
from google.genai import types

# 환경 변수 로드
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini AI 클라이언트 초기화 (AI 에이전트의 뇌)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SEARCH_QUERIES = [
    "목동 영유 설명회", "목동 폴리 모집", "목동 라이즈 설명회",
    "목동 프랜시스파커 입학", "목동 SLP 모집", "목동 영어유치원"
]

DB_FILE = "sent_posts.json"

def load_sent_posts():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_sent_posts(sent_set):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_set), f, ensure_ascii=False, indent=2)

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }).encode("utf-8")
    context = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, context=context)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

# [AI Agent 핵심] Gemini LLM을 통한 문맥 분석 및 필터링/요약
def analyze_post_with_ai(title, description):
    if not ai_client:
        return True, "AI 분석 미설정 (기본 알림)"

    prompt = f"""
    너는 서울 목동 지역 영어유치원(영유) 입학/설명회 소식을 모니터링하는 전문 AI 에이전트다.
    다음 게시글의 제목과 요약 내용을 읽고 검토해라.

    [게시글 제목]: {title}
    [게시글 내용]: {description}

    다음 규칙에 따라 판단하고 반드시 JSON 형식으로만 응답해라:
    1. is_relevant (boolean): 이 글이 목동 지역 주요 영어유치원(폴리, 라이즈, 프랜시스파커, SLP, 월넛, PSA 등)의 '실제 설명회 일정', '원아 모집 공고', '레벨테스트 안내' 또는 '유용한 학부모 참석/대기 후기'인가?
       (단순 학원 마케팅, 부동산 글, 무관한 광고글, 단어만 낚시성으로 포함된 글은 false)
    2. summary (string): is_relevant가 true인 경우, 핵심 정보(대상 연령, 일시, 주요 특징 등)를 2~3줄로 깔끔하게 요약해라. false인 경우 빈 문자열.

    응답 JSON 포맷:
    {{"is_relevant": true/false, "summary": "요약 내용..."}}
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        res_json = json.loads(response.text)
        return res_json.get("is_relevant", False), res_json.get("summary", "")
    except Exception as e:
        print(f"Gemini AI 분석 실패: {e}")
        return True, "AI 요약 생성 중 오류 발생"

def run_agent():
    sent_posts = load_sent_posts()
    new_sent_posts = set(sent_posts)
    found_count = 0

    print("=== [AI Agent] 목동 영유 게시물 수집 및 분석 시작 ===")

    for query in SEARCH_QUERIES:
        encoded_kw = urllib.parse.quote(query)
        rss_urls = [
            f"https://search.naver.com/search.naver?where=rss&query={encoded_kw}",
            f"https://search.naver.com/search.naver?where=kin_rss&query={encoded_kw}"
        ]
        
        for rss_url in rss_urls:
            try:
                req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
                context = ssl._create_unverified_context()
                with urllib.request.urlopen(req, context=context, timeout=8) as resp:
                    xml_data = resp.read()
                    root = ET.fromstring(xml_data)
                    
                    for item in root.findall('.//item')[:3]:
                        title = item.find('title').text or ""
                        description = item.find('description').text or ""
                        link = item.find('link').text or ""
                        
                        title_clean = title.replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                        desc_clean = description.replace('<b>', '').replace('</b>', '')

                        if link and link not in sent_posts:
                            is_relevant, ai_summary = analyze_post_with_ai(title_clean, desc_clean)
                            
                            if is_relevant:
                                msg = (
                                    f"🤖 <b>[AI Agent 영유 소식 브리핑]</b>\n\n"
                                    f"<b>📌 제목:</b> {title_clean}\n\n"
                                    f"<b>💡 AI 핵심 요약:</b>\n{ai_summary}\n\n"
                                    f"👉 <a href='{link}'>게시글 바로가기</a>"
                                )
                                send_telegram_msg(msg)
                                new_sent_posts.add(link)
                                found_count += 1
                            else:
                                new_sent_posts.add(link)
            except Exception as e:
                continue

    save_sent_posts(new_sent_posts)
    print(f"=== 완료: {found_count}건의 유의미한 소식을 AI가 요약 발송했습니다. ===")

if __name__ == "__main__":
    run_agent()
