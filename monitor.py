import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import ssl
import os
import json
import re

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# [업그레이드 1] 영문/한글 혼용 및 유의어 매칭 사전 (K-Skill 기반 필터링)
KEYWORD_MAP = {
    "폴리": ["폴리", "poly", "엠폴리", "mpoly"],
    "라이즈": ["라이즈", "rise"],
    "프랜시스파커": ["프랜시스파커", "프란시스파커", "francis parker"],
    "SLP": ["slp", "에스엘피"],
    "월넛": ["월넛", "walnut"],
    "엘란": ["엘란", "elan"],
    "PSA": ["psa", "피에스에이"],
    "ECC": ["ecc", "이씨씨"],
    "영유": ["영유", "영어유치원", "영어 유치원"]
}

# 검색 시 사용할 대표 키워드
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
        "parse_mode": "HTML"
    }).encode("utf-8")
    context = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, context=context)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

# [업그레이드 2] 띄어쓰기 및 특수문자 제거 후 유의어 검사 로직
def is_relevant_post(title, summary):
    # 텍스트를 소문자로 통일하고 띄어쓰기, 특수문자 완벽 제거
    text = (title + " " + summary).lower()
    text_clean = re.sub(r'[^가-힣a-z0-9]', '', text)
    
    # '목동'이라는 단어가 텍스트에 존재하는지 1차 확인
    if "목동" not in text_clean:
        return False
        
    # 영유 이름이 텍스트에 포함되어 있는지 2차 확인
    for key, aliases in KEYWORD_MAP.items():
        for alias in aliases:
            alias_clean = re.sub(r'[^가-힣a-z0-9]', '', alias)
            if alias_clean in text_clean:
                # 설명회, 입학, 모집, 원아 등의 목적 단어가 있는지 3차 확인
                if any(word in text_clean for word in ["설명회", "모집", "입학", "레벨테스트", "입테", "원아"]):
                    return True
    return False

def check_smart_blogs():
    sent_posts = load_sent_posts()
    new_sent_posts = set(sent_posts)
    
    print("=== [지능형 K-필터 적용] 검색 시작 ===")

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
                    
                    for item in root.findall('.//item')[:5]:
                        title = item.find('title').text or ""
                        summary = item.find('description').text or ""
                        link = item.find('link').text or ""
                        
                        # [적용] 지능형 필터 통과 여부 확인
                        if link not in sent_posts and is_relevant_post(title, summary):
                            title_clean = title.replace('<b>', '').replace('</b>', '')
                            msg = f"📢 <b>[목동 영유 스마트 감지]</b>\n\n<b>제목:</b> {title_clean}\n\n👉 <a href='{link}'>게시글 바로가기</a>"
                            send_telegram_msg(msg)
                            new_sent_posts.add(link)
            except Exception:
                continue

    save_sent_posts(new_sent_posts)

if __name__ == "__main__":
    check_smart_blogs()
