#!/usr/bin/env python3
"""
OFF90 데일리 리포트 뉴스 수집
- 월드컵: 경기결과 > 주목이슈 > 프리뷰 우선순위
- 이적시장: 오피셜 > 유력설(로마노 등) > 찌라시 우선순위, 영어 번역 포함
"""
import re
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False

MAX_PER_SECTION = 5
SKIP_KEYWORDS = ["광고", "이벤트", "경품", "무료 관람", "티켓 할인"]

# ── 월드컵 피드 ────────────────────────────────────────────────
WORLDCUP_FEEDS = [
    "https://news.google.com/rss/search?q=2026+FIFA+월드컵+경기+결과&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=월드컵+조별리그+경기결과+2026&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=2026+월드컵+이변+이슈&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=월드컵+2026+경기+전망+예정&hl=ko&gl=KR&ceid=KR:ko",
]

# ── 이적시장 피드 (영문 포함) ──────────────────────────────────
TRANSFER_FEEDS = [
    # 오피셜 / 로마노
    "https://news.google.com/rss/search?q=fabrizio+romano+%22here+we+go%22+transfer&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=football+transfer+official+confirmed+2025&hl=en&gl=GB&ceid=GB:en",
    # 유력설
    "https://news.google.com/rss/search?q=fabrizio+romano+transfer+exclusive&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=Ben+Jacobs+OR+Ornstein+transfer+exclusive&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=premier+league+transfer+rumour+2025&hl=en&gl=GB&ceid=GB:en",
    # 한국 선수
    "https://news.google.com/rss/search?q=Son+Heungmin+OR+Lee+Kangin+OR+Kim+Minjae+transfer&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=손흥민+이강인+김민재+황희찬+이적&hl=ko&gl=KR&ceid=KR:ko",
]


def _translate(text):
    """영어 → 한국어 번역. 실패 시 원문 반환."""
    if not TRANSLATOR_AVAILABLE:
        return text
    try:
        result = GoogleTranslator(source="auto", target="ko").translate(text[:500])
        return result or text
    except Exception:
        return text


def _is_english(text):
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    return ascii_ratio > 0.7


def _worldcup_priority(title):
    t = title.lower()
    # 1순위: 경기 결과
    if any(k in t for k in ["결과", "스코어", "score", "result", "beats", "wins",
                             "무승부", "승리", "패배", "골", "draw", "defeat", "vs "]):
        return 3
    # 2순위: 주목할 이슈
    if any(k in t for k in ["이변", "upset", "shock", "surprise", "신들린",
                             "amazing", "outstanding", "감동", "충격"]):
        return 2
    # 3순위: 프리뷰
    return 1


def _transfer_priority(title):
    t = title.lower()
    # 1순위: 오피셜
    if any(k in t for k in ["here we go", "official", "오피셜", "confirmed",
                             "완료", "signs", "joins", "announces", "done deal",
                             "deal done", "agreement reached"]):
        return 3
    # 2순위: 유력 (로마노/공신력 기자)
    if any(k in t for k in ["romano", "ornstein", "ben jacobs", "fabrizio",
                             "exclusive", "유력", "협상", "접촉", "관심", "접근"]):
        return 2
    # 3순위: 찌라시
    return 1


CUTOFF_HOURS = 18  # 오전 8시 기준 18시간 이내 기사만 수집


def _within_cutoff(pub_str):
    """pubDate가 CUTOFF_HOURS 이내인지 확인. 날짜 파싱 실패 시 통과."""
    if not pub_str:
        return True
    try:
        pub_dt = parsedate_to_datetime(pub_str)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=CUTOFF_HOURS)
        return pub_dt >= cutoff
    except Exception:
        return True


def _parse_rss(url, max_items=10):
    articles = []
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OFF90Bot/1.0)"},
            timeout=12,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return articles
        for item in channel.findall("item")[:max_items]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub = item.findtext("pubDate", "").strip()
            if not title or not link:
                continue
            if not _within_cutoff(pub):
                continue  # 24시간 초과 기사 제외
            if any(kw in title for kw in SKIP_KEYWORDS):
                continue
            clean = re.sub(r"\s*-\s*[^-]{1,40}$", "", title).strip()
            articles.append({"title": clean, "link": link, "published": pub})
    except Exception as e:
        print(f"[RSS 오류] {url[:60]}: {e}")
    return articles


def _collect(feeds, priority_fn, max_per_feed=8):
    seen, results = set(), []
    for url in feeds:
        for art in _parse_rss(url, max_per_feed):
            title = art["title"]
            if title in seen:
                continue
            seen.add(title)

            # 영어 기사 번역
            if _is_english(title):
                art["title_ko"] = _translate(title)
                art["lang"] = "en"
            else:
                art["title_ko"] = title
                art["lang"] = "ko"

            art["priority"] = priority_fn(title)
            results.append(art)

    # 우선순위 내림차순 정렬 후 상위 MAX_PER_SECTION개
    results.sort(key=lambda x: x["priority"], reverse=True)
    return results[:MAX_PER_SECTION]


def scrape_news():
    return {
        "worldcup": _collect(WORLDCUP_FEEDS, _worldcup_priority),
        "transfer": _collect(TRANSFER_FEEDS, _transfer_priority),
    }


def _priority_label_wc(p):
    return {3: "📋 경기결과", 2: "⚡ 주목이슈", 1: "🔭 프리뷰"}.get(p, "")


def _priority_label_tr(p):
    return {3: "🟢 오피셜", 2: "🟡 유력설", 1: "🔴 찌라시"}.get(p, "")


def format_kakao_message(news):
    today = datetime.now().strftime("%m/%d (%a)")
    for en, ko in {"Mon":"월","Tue":"화","Wed":"수","Thu":"목",
                   "Fri":"금","Sat":"토","Sun":"일"}.items():
        today = today.replace(en, ko)

    lines = [f"⚽ OFF90 데일리 리포트 {today}\n"]

    # 월드컵
    lines.append("━━━ 🏆 월드컵 뉴스 ━━━")
    wc = news.get("worldcup", [])
    if wc:
        for i, art in enumerate(wc, 1):
            label = _priority_label_wc(art.get("priority", 1))
            lines.append(f"\n{i}. [{label}] {art['title_ko']}")
            lines.append(f"   🔗 {art['link']}")
    else:
        lines.append("(수집된 기사 없음)")

    lines.append("")

    # 이적시장
    lines.append("━━━ 🔄 해외 이적시장 ━━━")
    tr = news.get("transfer", [])
    if tr:
        for i, art in enumerate(tr, 1):
            label = _priority_label_tr(art.get("priority", 1))
            title_display = art["title_ko"]
            if art.get("lang") == "en":
                title_display += f"\n   ({art['title']})"
            lines.append(f"\n{i}. [{label}] {title_display}")
            lines.append(f"   🔗 {art['link']}")
    else:
        lines.append("(수집된 기사 없음)")

    lines.append("\n━━━━━━━━━━━━━━━━━")
    lines.append("콘텐츠 만들 기사를 답장해 주세요.")
    lines.append("예) 월컵2 / 이적1")
    lines.append("\n👇 OFF90봇에서 승인")
    lines.append("https://pf.kakao.com/_BsxgnX/chat")
    return "\n".join(lines)


if __name__ == "__main__":
    news = scrape_news()
    print(f"월드컵: {len(news['worldcup'])}개 / 이적시장: {len(news['transfer'])}개\n")
    print(format_kakao_message(news))
