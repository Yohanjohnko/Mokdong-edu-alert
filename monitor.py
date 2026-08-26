import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import ssl
import os
import json

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

TARGET_KEYWORDS = [
    "목동 폴리 설명회", "목동 라이즈 모집", "목동 프랜시스파커 설명회",
    "목동 SLP 모집", "목동 영어유치원 설명회", "목동 영유 원아모집"
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
        print("[오류] TELEGRAM_TOKEN 또는 CHAT_ID가 설정되지 않았습니다.")
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
        with urllib.request.urlopen(req, context=context) as response:
            print("텔레그램 전송 성공")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def check_blogs():
    sent_posts = load_sent_posts()
    new_sent_posts = set(sent_posts)
    found_count = 0

    print("=== 목동 영유 최신 공고 검색 시작 ===")

    for kw in TARGET_KEYWORDS:
        encoded_kw = urllib.parse.quote(kw)
        naver_rss = f"https://search.naver.com/search.naver?where=rss&query={encoded_kw}"
        
        try:
            req = urllib.request.Request(
                naver_rss, 
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            )
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=context, timeout=10) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                
                for item in root.findall('.//item')[:3]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    
                    title_clean = title.replace('<b>', '').replace('</b>', '').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
                    
                    if link and link not in sent_posts:
                        msg = f"📢 <b>[목동 영유 신규 공고 감지]</b>\n\n<b>키워드:</b> {kw}\n<b>제목:</b> {title_clean}\n\n👉 <a href='{link}'>게시글 바로가기</a>"
                        send_telegram_msg(msg)
                        new_sent_posts.add(link)
                        found_count += 1
        except Exception as e:
            print(f"[{kw}] 검색 중 예외 발생: {e}")

    save_sent_posts(new_sent_posts)
    print(f"검색 완료: 신규 알림 {found_count}건 전송됨.")

if __name__ == "__main__":
    check_blogs()
