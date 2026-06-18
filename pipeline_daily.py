#!/usr/bin/env python3
"""
OFF90 데일리 파이프라인
뉴스 수집 → 전체 목록 Discord 발송 → 사용자가 번호로 선택
"""
import re, sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.news_scraper import scrape_news
from tools.discord_bot import send_message
import tools.state_manager as sm

AGGREGATE_PATTERNS = [
    "일정", "모아보기", "순위", "스케줄", "캘린더",
    "전 경기", "중계 일정", "하이라이트 모음", "결과 모음",
    "조별 예선 순위", "경기 일정", "대진표", "조 편성",
    "라이브 스코어", "라이브스코어", "경기 결과 -",
    "조별 예선 1차전 라이브", "조별 예선 2차전 라이브", "조별 예선 3차전 라이브",
]

TEAM_NAMES = [
    "브라질","모로코","프랑스","독일","스페인","아르헨티나","잉글랜드","포르투갈",
    "일본","한국","대한민국","미국","멕시코","네덜란드","이탈리아","벨기에",
    "크로아티아","세네갈","가나","나이지리아","호주","사우디","이란","카타르",
    "캐나다","에콰도르","우루과이","칠레","콜롬비아","페루","폴란드","덴마크",
    "스위스","오스트리아","우크라이나","튀르키예",
    "Brazil","Morocco","France","Germany","Spain","Argentina","England","Portugal",
    "Japan","Korea","USA","Mexico","Netherlands","Italy","Belgium","Croatia",
]


def is_aggregate(title: str) -> bool:
    return any(p in title for p in AGGREGATE_PATTERNS)


def has_match_data(title: str) -> bool:
    has_score = bool(re.search(r"\d+\s*[-:]\s*\d+", title))
    has_team  = any(t in title for t in TEAM_NAMES)
    return has_score or has_team


def format_news_list(news: dict) -> tuple:
    """뉴스 목록을 Discord 텍스트 + 번호 dict로 변환"""
    today = datetime.now().strftime("%Y.%m.%d")
    lines = [f"⚽ **OFF90 오늘의 뉴스** — {today}\n"]
    numbered = {}
    idx = 1

    wc_items = [
        a for a in news.get("worldcup", [])
        if not is_aggregate(a.get("title_ko") or a.get("title", ""))
    ]
    tr_items = news.get("transfer", [])

    if wc_items:
        lines.append("🏆 **월드컵 경기결과**")
        for a in wc_items[:6]:
            title = a.get("title_ko") or a.get("title", "")
            lines.append(f"**{idx}.** {title[:75]}")
            numbered[str(idx)] = ["worldcup", a]
            idx += 1

    if tr_items:
        if wc_items:
            lines.append("")
        lines.append("🔄 **이적설**")
        for a in tr_items[:6]:
            title = a.get("title_ko") or a.get("title", "")
            rel = {3: "🟢", 2: "🟡", 1: "🔴"}.get(a.get("priority", 1), "🔴")
            lines.append(f"**{idx}.** {rel} {title[:75]}")
            numbered[str(idx)] = ["transfer", a]
            idx += 1

    if not numbered:
        return None, {}

    lines.append(f"\n몇 번 콘텐츠로 만들까요? **번호**를 입력해주세요.")
    return "\n".join(lines), numbered


def main():
    state = sm.load()
    if state.get("status") not in ("idle", "published", None):
        print(f"진행 중인 콘텐츠 있음 (상태: {state['status']}). 건너뜀.")
        return

    print("뉴스 수집 중...")
    news = scrape_news()

    for kind in ("worldcup", "transfer"):
        for a in news.get(kind, []):
            title = a.get("title_ko") or a.get("title", "")
            flag = "🚫" if is_aggregate(title) else "✅"
            print(f"  [{kind}] {flag} {title[:70]}")

    msg_text, numbered = format_news_list(news)

    if not numbered:
        send_message("⚽ **OFF90**\n\n오늘은 발행할 만한 뉴스가 없습니다.")
        return

    msg = send_message(msg_text)
    sm.save({
        "status": "awaiting_story_selection",
        "news_list": numbered,
        "last_message_id": msg["id"],
    })
    print(f"뉴스 {len(numbered)}개 Discord 발송 완료.")


if __name__ == "__main__":
    main()
