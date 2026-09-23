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

NEWS_QUERIES = ["부동산", "재테크", "경제"]
SPLIT_MARKER = "=====TOPIC====="


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


# 2. 부동산/재테크/경제 최신 화제 기사 수집 (링크까지 포함해서 목록화)
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

listing = "\n".join(
    f"{i + 1}. 제목: {c['title']}\n   내용: {c['desc']}\n   링크: {c['link']}"
    for i, c in enumerate(candidates)
)

# 3. Gemini에게 화제성 Top 2 주제를 고르고, johnko_ 블로그 표준 양식에 맞춰 초안 작성 요청
prompt = f"""
너는 네이버 블로그 "johnko_"(부동산 정책·재테크·라이프스타일 카테고리)를 운영하는 블로거의 원고 작성을 돕는 AI 에이전트다.
아래 정해진 작성 규칙을 반드시 그대로 따라야 한다.

[기사 목록 — 최근 부동산/재테크/경제 뉴스]
{listing}

[1단계] 위 기사 중 블로그 독자가 가장 관심 가질 화제성 있는 주제 2개를 골라라.

[2단계] 각 주제마다 아래 양식을 정확히 지켜서 원고를 작성해라.

--- 작성 규칙 (johnko_ 블로그 표준) ---
- 마크다운 기호(*, #, -, [], () 등) 절대 사용 금지 — 네이버 에디터에서 안 렌더링됨
- 소제목은 ① ② ③ 번호 또는 【 】 괄호 형식만 사용
- 표 대신 화살표(→) 표기 사용
- 확정되지 않은 정책 내용은 "검토 중이다", "~로 거론된다", "~로 관측된다" 같은 완곡한 표현 사용, 단정적 서술 금지
- 개인 생각 문단은 반드시 "✍️ 개인 생각"으로 시작
- 부동산 정책/재건축 관련 주제일 때만: 글쓴이는 재건축을 앞둔 1주택 실거주자이며, 공급 확대와 민간 재건축 활성화를 지지하는 입장에서 논조를 잡되 정부 정책을 과도하게 비판하는 어조는 피할 것. 이 주제가 아니면 이 프레이밍을 억지로 적용하지 말 것
- 아이 이름·나이·기관명, 회사명, 아파트 동/호수 등 특정 개인정보는 절대 언급하지 말 것
- 참고 링크는 본문 안에 넣지 말고 맨 마지막 별도 항목으로만 표기
- 해시태그는 10~15개, 구체적인 용어로만 (예: "부동산", "재테크"처럼 너무 넓은 단어는 제외)
- 본문 분량은 1,500자 이상, 최소 4~5개 문단 구성 (도입 - 핵심 내용 - 앞으로의 영향 - 개인 생각 순서)

--- 출력 형식 (아래 구조를 그대로, 두 주제 사이는 반드시 "{SPLIT_MARKER}" 한 줄로만 구분) ---

【제목 후보】
1. (제목1)
2. (제목2)
3. (제목3)

【본문】
(도입부)

① (핵심 내용 소제목)
(내용)

② (앞으로의 영향 소제목)
(내용)

③ ✍️ 개인 생각
(내용)

【참고링크】
(위 기사 목록에서 이 주제에 해당하는 기사의 실제 링크를 그대로 복사)

【해시태그】
#태그1 #태그2 ... (10~15개)

{SPLIT_MARKER}

(두 번째 주제도 동일한 구조로 반복)
"""

candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
draft_text = None
for model_name in candidate_models:
    try:
        print(f"[{model_name}] 초안 생성 시도 중...")
        response = client.models.generate_content(model=model_name, contents=prompt)
        if response and response.text:
            draft_text = response.text.strip()
            print(f"성공된 모델: {model_name}")
            break
    except Exception as e:
        print(f"[{model_name}] 호출 실패 ({e}). 다음 백업 모델로 재시도합니다.")

if not draft_text:
    raise RuntimeError("모든 Gemini 모델 호출에 실패했습니다.")

# 4. 텔레그램 전송 — 주제별로 메시지를 분리해서 전송 (길이 제한 및 가독성 때문)
url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
parts = [p.strip() for p in draft_text.split(SPLIT_MARKER) if p.strip()]
if not parts:
    parts = [draft_text]

for idx, part in enumerate(parts, 1):
    header = f"📝 [블로그 초안 {idx}/{len(parts)}]\n\n"
    payload = {"chat_id": CHAT_ID, "text": header + part}
    telegram_response = requests.post(url, json=payload)
    telegram_response.raise_for_status()

print(f"블로그 초안 텔레그램 전송 완료! ({len(parts)}건)")
