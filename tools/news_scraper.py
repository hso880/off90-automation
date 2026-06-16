#!/usr/bin/env python3
"""
OFF90 데일리 리포트 뉴스 수집
- 월드컵: 경기결과 > 주목이슈 > 프리뷰 (18h 컷오프)
- 이적시장: 오피셜 > 유력설 > 찌라시 (24h 컷오프), 영어 번역 포함
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
WORLDCUP_CUTOFF_HOURS = 24   # 오전 8시 기준 24시간 이내
TRANSFER_CUTOFF_HOURS = 24   # 오전 8시 기준 24시간 이내
SKIP_KEYWORDS = ["광고", "이벤트", "경품", "무료 관람", "티켓 할인"]

# ── 월드컵 피드 ────────────────────────────────────────────────
WORLDCUP_FEEDS = [
    "https://news.google.com/rss/search?q=2026+FIFA+월드컵+경기+결과&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=월드컵+조별리그+경기결과+2026&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=2026+월드컵+이변+이슈+충격&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=월드컵+2026+경기+전망+예정&hl=ko&gl=KR&ceid=KR:ko",
]

# ── 이적시장 피드 (영문 + 국문) ───────────────────────────────
TRANSFER_FEEDS = [
    # 🟢 오피셜 우선
    "https://news.google.com/rss/search?q=fabrizio+romano+%22here+we+go%22&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=football+transfer+official+confirmed+signed&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=해외축구+이적+오피셜+완료&hl=ko&gl=KR&ceid=KR:ko",
    # 🟡 유력설
    "https://news.google.com/rss/search?q=fabrizio+romano+transfer+exclusive+2025&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=David+Ornstein+OR+Ben+Jacobs+transfer&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=EPL+라리가+분데스리가+이적설+유력&hl=ko&gl=KR&ceid=KR:ko",
    # 한국 선수
    "https://news.google.com/rss/search?q=Son+Heungmin+OR+Lee+Kangin+OR+Kim+Minjae+transfer&hl=en&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=손흥민+이강인+김민재+황희찬+이적&hl=ko&gl=KR&ceid=KR:ko",
]


def _shorten_url(url):
    """TinyURL API로 링크 단축. 실패 시 도메인만 표시."""
    try:
        r = requests.get(
            f"https://tinyurl.com/api-create.php?url={url}",
            timeout=5,
        )
        if r.ok and r.text.strip().startswith("http"):
            return r.text.strip()
    except Exception:
        pass
    # 폴백: 도메인 + 말줄임
    match = re.search(r"https?://([^/]+)", url)
    domain = match.group(1) if match else "링크"
    return f"({domain})"


def _translate(text):
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
    if any(k in t for k in ["결과", "스코어", "score", "result", "beats", "wins",
                             "무승부", "승리", "패배", "골", "draw", "defeat", "vs "]):
        return 3
    if any(k in t for k in ["이변", "upset", "shock", "surprise", "신들린",
                             "amazing", "outstanding", "감동", "충격"]):
        return 2
    return 1


def _transfer_priority(title):
    t = title.lower()

    # 1순위: 오피셜 (확정/완료)
    OFFICIAL = [
        "here we go",
        "official", "confirmed", "done deal", "deal done", "agreement reached",
        "signs", "signed", "joins", "joined", "seals", "completes", "medical",
        "passes medical", "undergoes medical", "announces", "unveiled", "set to join",
        "오피셜", "이적 확정", "계약 완료", "서명 완료", "합류 확정", "영입 완료",
    ]
    if any(k in t for k in OFFICIAL):
        return 3

    # 2순위: 유력설 (공신력 기자 or 구체적 협상)
    CREDIBLE = [
        "romano", "fabrizio", "ornstein", "ben jacobs", "florian plettenberg",
        "matteo moretto", "ekrem konur",
        "exclusive", "in talks", "close to", "nearing", "bid", "offer",
        "approach", "contact", "interested", "personal terms", "fee agreed", "pushing",
        "유력", "협상", "접촉", "관심", "접근", "이적설", "영입 추진", "협의 중",
    ]
    if any(k in t for k in CREDIBLE):
        return 2

    # "X to [Club]" 패턴 — 영어 이적 저널리즘의 확정/유력 표현
    # e.g. "Amorim to AC Milan", "Mbappe to Real Madrid"
    if re.search(r'[A-Z][a-z]+ to [A-Z]', title):
        return 2

    # 한국어 "X, Y로 이적/합류" 패턴
    if re.search(r'[가-힣].{0,5}(으로|로)\s*(이적|합류|이동)', title):
        return 2

    return 1


def _within_cutoff(pub_str, hours):
    if not pub_str:
        return True
    try:
        pub_dt = parsedate_to_datetime(pub_str)
        return pub_dt >= datetime.now(timezone.utc) - timedelta(hours=hours)
    except Exception:
        return True


def _parse_rss(url, max_items=10, cutoff_hours=24):
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
            if not _within_cutoff(pub, cutoff_hours):
                continue
            if any(kw in title for kw in SKIP_KEYWORDS):
                continue
            clean = re.sub(r"\s*-\s*[^-]{1,40}$", "", title).strip()
            articles.append({"title": clean, "link": link, "published": pub})
    except Exception as e:
        print(f"[RSS 오류] {url[:60]}: {e}")
    return articles


def _collect(feeds, priority_fn, cutoff_hours, max_per_feed=8):
    seen, results = set(), []
    for url in feeds:
        for art in _parse_rss(url, max_per_feed, cutoff_hours):
            title = art["title"]
            if title in seen:
                continue
            seen.add(title)

            if _is_english(title):
                art["title_ko"] = _translate(title)
                art["lang"] = "en"
            else:
                art["title_ko"] = title
                art["lang"] = "ko"

            art["priority"] = priority_fn(title)
            art["short_link"] = _shorten_url(art["link"])
            results.append(art)

    results.sort(key=lambda x: x["priority"], reverse=True)
    return results[:MAX_PER_SECTION]


def scrape_news():
    return {
        "worldcup": _collect(WORLDCUP_FEEDS, _worldcup_priority, WORLDCUP_CUTOFF_HOURS),
        "transfer": _collect(TRANSFER_FEEDS, _transfer_priority, TRANSFER_CUTOFF_HOURS),
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
    lines.append("━━━ 🏆 월드컵 ━━━")
    wc = news.get("worldcup", [])
    if wc:
        for i, art in enumerate(wc, 1):
            label = _priority_label_wc(art.get("priority", 1))
            lines.append(f"\n{i}. [{label}]")
            lines.append(f"   {art['title_ko']}")
            lines.append(f"   🔗 {art['short_link']}")
    else:
        lines.append("(18h 이내 기사 없음)")

    lines.append("")

    # 이적시장
    lines.append("━━━ 🔄 이적시장 ━━━")
    tr = news.get("transfer", [])
    if tr:
        for i, art in enumerate(tr, 1):
            label = _priority_label_tr(art.get("priority", 1))
            lines.append(f"\n{i}. [{label}]")
            lines.append(f"   {art['title_ko']}")
            if art.get("lang") == "en":
                lines.append(f"   ({art['title']})")
            lines.append(f"   🔗 {art['short_link']}")
    else:
        lines.append("(24h 이내 이적 뉴스 없음)")

    lines.append("\n━━━━━━━━━━━━━━━")
    lines.append("콘텐츠 만들 기사를 답장해 주세요.")
    lines.append("예) 월컵2 / 이적1")
    lines.append("\n👇 OFF90봇에서 승인")
    lines.append("https://pf.kakao.com/_BsxgnX/chat")
    return "\n".join(lines)


if __name__ == "__main__":
    news = scrape_news()
    print(f"월드컵: {len(news['worldcup'])}개 / 이적시장: {len(news['transfer'])}개\n")
    print(format_kakao_message(news))
