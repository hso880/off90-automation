#!/usr/bin/env python3
"""
OFF90 데일리 뉴스 수집 — 월드컵 / 해외축구 이적시장 2섹션
"""
import re
import xml.etree.ElementTree as ET
import requests
from datetime import datetime


WORLDCUP_FEEDS = [
    "https://news.google.com/rss/search?q=2026+FIFA+월드컵&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=한국+축구+국가대표+월드컵+2026&hl=ko&gl=KR&ceid=KR:ko",
]

TRANSFER_FEEDS = [
    "https://news.google.com/rss/search?q=해외축구+이적+이적시장&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=손흥민+이강인+황희찬+김민재+이적&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=football+transfer+EPL+라리가+분데스리가&hl=ko&gl=KR&ceid=KR:ko",
]

SKIP_KEYWORDS = ["광고", "이벤트", "경품", "무료 관람", "티켓 할인"]


def _parse_rss(url, max_items=5):
    articles = []
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OFF90Bot/1.0)"},
            timeout=10,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return articles
        for item in channel.findall("item")[:max_items]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            if not title or not link:
                continue
            if any(kw in title for kw in SKIP_KEYWORDS):
                continue
            # Google News " - 언론사명" 제거
            clean = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
            articles.append({"title": clean, "link": link})
    except Exception as e:
        print(f"[RSS 오류] {url}: {e}")
    return articles


def _collect(feeds, max_per_feed=4, total_max=5):
    seen, results = set(), []
    for url in feeds:
        for art in _parse_rss(url, max_per_feed):
            if art["title"] in seen:
                continue
            seen.add(art["title"])
            results.append(art)
            if len(results) >= total_max:
                return results
    return results


def scrape_news():
    return {
        "worldcup": _collect(WORLDCUP_FEEDS, max_per_feed=4, total_max=5),
        "transfer": _collect(TRANSFER_FEEDS, max_per_feed=4, total_max=5),
    }


def format_kakao_message(news):
    today = datetime.now().strftime("%m/%d (%a)")
    for en, ko in {"Mon":"월","Tue":"화","Wed":"수","Thu":"목","Fri":"금","Sat":"토","Sun":"일"}.items():
        today = today.replace(en, ko)

    lines = [f"⚽ OFF90 데일리 리포트 {today}\n"]

    lines.append("🏆 월드컵 뉴스")
    wc = news.get("worldcup", [])
    if wc:
        for i, art in enumerate(wc, 1):
            lines.append(f"  {i}. {art['title']}")
    else:
        lines.append("  (수집된 기사 없음)")

    lines.append("")
    lines.append("🔄 해외축구 이적시장")
    tr = news.get("transfer", [])
    if tr:
        for i, art in enumerate(tr, 1):
            lines.append(f"  {i}. {art['title']}")
    else:
        lines.append("  (수집된 기사 없음)")

    lines.append("\n콘텐츠 만들 기사를 답장해 주세요.")
    lines.append("예) 월컵2 / 이적3")
    lines.append("\n👇 OFF90봇에서 승인")
    lines.append("https://pf.kakao.com/_BsxgnX/chat")
    return "\n".join(lines)


if __name__ == "__main__":
    news = scrape_news()
    print(f"월드컵: {len(news['worldcup'])}개 / 이적시장: {len(news['transfer'])}개\n")
    print(format_kakao_message(news))
