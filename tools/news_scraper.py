#!/usr/bin/env python3
"""
월드컵 관련 뉴스 RSS 수집
"""
import re
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
from datetime import datetime


FEEDS = [
    {
        "name": "구글뉴스_월드컵",
        "url": "https://news.google.com/rss/search?q=2026+월드컵+FIFA&hl=ko&gl=KR&ceid=KR:ko",
    },
    {
        "name": "구글뉴스_한국축구",
        "url": "https://news.google.com/rss/search?q=한국+축구+국가대표+2026&hl=ko&gl=KR&ceid=KR:ko",
    },
    {
        "name": "구글뉴스_이적시장",
        "url": "https://news.google.com/rss/search?q=축구+이적+손흥민+이강인&hl=ko&gl=KR&ceid=KR:ko",
    },
]

# 너무 뻔한 기사 필터 (광고성, 중복 소지)
SKIP_KEYWORDS = ["광고", "이벤트", "경품", "무료 관람"]


def _parse_rss(url, max_items=5):
    articles = []
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OFF90Bot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        channel = root.find("channel")
        if channel is None:
            return articles
        for item in channel.findall("item")[:max_items]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub = item.findtext("pubDate", "").strip()
            if not title or not link:
                continue
            if any(kw in title for kw in SKIP_KEYWORDS):
                continue
            articles.append({"title": title, "link": link, "published": pub})
    except Exception as e:
        print(f"[RSS 오류] {url}: {e}")
    return articles


def scrape_news(max_per_feed=5, total_max=10):
    seen = set()
    results = []
    for feed in FEEDS:
        for art in _parse_rss(feed["url"], max_per_feed):
            # Google News 타이틀에 붙는 " - 언론사명" 제거
            clean_title = re.sub(r"\s*-\s*[^-]+$", "", art["title"]).strip()
            if clean_title in seen:
                continue
            seen.add(clean_title)
            art["title"] = clean_title
            art["source"] = feed["name"]
            results.append(art)
            if len(results) >= total_max:
                break
        if len(results) >= total_max:
            break
    return results


def format_kakao_message(articles):
    today = datetime.now().strftime("%m/%d (%a)")
    # 요일 한국어 변환
    day_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목",
               "Fri": "금", "Sat": "토", "Sun": "일"}
    for en, ko in day_map.items():
        today = today.replace(en, ko)

    lines = [f"⚽ OFF90 뉴스 브리핑 {today}\n"]
    for i, art in enumerate(articles, 1):
        lines.append(f"{i}. {art['title']}")
    lines.append("\n콘텐츠로 만들 기사 번호를 답장해 주세요.")
    return "\n".join(lines)


if __name__ == "__main__":
    arts = scrape_news()
    print(f"수집된 기사: {len(arts)}개\n")
    print(format_kakao_message(arts))
