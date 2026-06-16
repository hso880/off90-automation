#!/usr/bin/env python3
"""
OFF90 데일리 리포트 뉴스 수집
- 월드컵: 경기결과 > 주목이슈 > 프리뷰 (24h 컷오프)
- 이적시장: 오피셜 > 유력설 > 찌라시 (24h 컷오프), 영어 번역 포함
  + Instagram 직접 스크래핑 (Romano 등) — Google News 우회
"""
import itertools
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

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False

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

# ── Instagram 직접 소스 ────────────────────────────────────────
# Google News가 못 잡는 실시간 SNS 포스트를 직접 수집
# priority_min: 해당 계정 게시물의 최소 신뢰도 (2=유력설, 3=오피셜)
INSTAGRAM_SOURCES = [
    {"username": "fabrizioromano",   "priority_min": 2, "label": "IG @fabrizioromano"},
    {"username": "david.ornstein",   "priority_min": 2, "label": "IG @david.ornstein"},
    {"username": "brentderksen",     "priority_min": 2, "label": "IG @brentderksen"},
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


def _scrape_instagram_account(username, cutoff_hours, priority_min=2):
    """instaloader로 공개 계정 최근 포스트 수집 (로그인 불필요)."""
    if not INSTALOADER_AVAILABLE:
        return []
    try:
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            quiet=True,
        )
        profile = instaloader.Profile.from_username(L.context, username)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)
        posts = []
        for post in itertools.islice(profile.get_posts(), 15):
            if post.date_utc.replace(tzinfo=timezone.utc) < cutoff:
                break
            caption = (post.caption or "").strip()
            if not caption:
                continue
            first_line = caption.split("\n")[0][:250]
            posts.append({
                "title": first_line,
                "link": f"https://www.instagram.com/p/{post.shortcode}/",
                "published": post.date_utc.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                "priority_min": priority_min,
                "source_label": f"IG @{username}",
            })
        print(f"[Instagram] @{username}: {len(posts)}개 수집")
        return posts
    except Exception as e:
        print(f"[Instagram 오류] @{username}: {e}")
        return []


def _collect_instagram(cutoff_hours):
    """Instagram 직접 소스 전체 수집 후 우선순위 계산."""
    items = []
    for src in INSTAGRAM_SOURCES:
        raw_posts = _scrape_instagram_account(
            src["username"], cutoff_hours, src.get("priority_min", 2)
        )
        for post in raw_posts:
            if _is_english(post["title"]):
                post["title_ko"] = _translate(post["title"])
                post["lang"] = "en"
            else:
                post["title_ko"] = post["title"]
                post["lang"] = "ko"
            keyword_priority = _transfer_priority(post["title"])
            post["priority"] = max(keyword_priority, post.get("priority_min", 2))
            post["short_link"] = _shorten_url(post["link"])
            items.append(post)
    return items


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
    worldcup = _collect(WORLDCUP_FEEDS, _worldcup_priority, WORLDCUP_CUTOFF_HOURS)

    # 이적시장: RSS + Instagram 직접 소스 병합
    transfer_rss = _collect(TRANSFER_FEEDS, _transfer_priority, TRANSFER_CUTOFF_HOURS)
    transfer_ig = _collect_instagram(TRANSFER_CUTOFF_HOURS)

    # 중복 제거 (제목 기준), IG 우선 포함
    seen = set()
    transfer_merged = []
    for art in transfer_ig + transfer_rss:
        key = art["title"][:60]
        if key not in seen:
            seen.add(key)
            transfer_merged.append(art)

    transfer_merged.sort(key=lambda x: x["priority"], reverse=True)

    return {
        "worldcup": worldcup,
        "transfer": transfer_merged[:MAX_PER_SECTION],
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
            source = art.get("source_label", "")
            source_str = f" · {source}" if source else ""
            lines.append(f"\n{i}. [{label}{source_str}]")
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
