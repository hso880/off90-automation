#!/usr/bin/env python3
"""
OFF90 데일리 파이프라인
뉴스 수집 → 네이버 이미지 검색 → Discord 사진 선택지 발송
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.news_scraper import scrape_news
from tools.naver_image import search_images, build_query
from tools.discord_bot import send_message, send_photo_options
import tools.state_manager as sm

# 집계·일정성 기사 제외 키워드
AGGREGATE_PATTERNS = [
    "일정", "모아보기", "순위", "스케줄", "캘린더",
    "전 경기", "중계 일정", "하이라이트 모음", "결과 모음",
    "조별 예선 순위", "경기 일정", "대진표", "조 편성",
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
    """집계·일정·순위 기사 여부"""
    return any(p in title for p in AGGREGATE_PATTERNS)


def has_match_data(title: str) -> bool:
    """팀명 또는 스코어가 포함된 실제 경기 기사 여부"""
    has_score = bool(re.search(r"\d+\s*[-:]\s*\d+", title))
    has_team  = any(t in title for t in TEAM_NAMES)
    return has_score or has_team


def select_top_story(news: dict):
    # 월드컵: 집계 기사 제외 + 팀명/스코어 필수
    wc_candidates = [
        a for a in news.get("worldcup", [])
        if a.get("priority", 0) >= 2
        and not is_aggregate(a.get("title_ko") or a.get("title", ""))
        and has_match_data(a.get("title_ko") or a.get("title", ""))
    ]
    if wc_candidates:
        return "worldcup", wc_candidates[0]

    # 이적: 신뢰도 유력 이상
    tr_candidates = [
        a for a in news.get("transfer", [])
        if a.get("priority", 0) >= 2
    ]
    if tr_candidates:
        return "transfer", tr_candidates[0]

    # 폴백: 집계만 아니면 뭐든
    for kind in ("worldcup", "transfer"):
        for a in news.get(kind, []):
            title = a.get("title_ko") or a.get("title", "")
            if not is_aggregate(title):
                return kind, a

    return None, None


def main():
    state = sm.load()
    if state.get("status") not in ("idle", "published", None):
        print(f"진행 중인 콘텐츠 있음 (상태: {state['status']}). 건너뜀.")
        return

    print("뉴스 수집 중...")
    news = scrape_news()

    # 수집된 뉴스 요약 출력
    for kind in ("worldcup", "transfer"):
        for a in news.get(kind, []):
            title = a.get("title_ko") or a.get("title", "")
            agg = "🚫집계" if is_aggregate(title) else "✅"
            match = "📊경기데이터" if has_match_data(title) else "❌데이터없음"
            print(f"  [{kind}] p={a.get('priority',0)} {agg} {match} | {title[:60]}")

    content_type, story = select_top_story(news)

    if not story:
        send_message(
            "⚽ **OFF90**\n\n오늘은 발행할 만한 경기 결과 또는 이적 뉴스가 없습니다.\n"
            "(집계·일정 기사 제외 후 남은 뉴스 없음)"
        )
        print("발행 가능한 뉴스 없음.")
        return

    title = story.get("title_ko") or story.get("title", "")
    print(f"\n선택: [{content_type}] {title}")

    # 이미지 검색 쿼리 구성
    data = {}
    if content_type == "worldcup":
        for name, code in [
            ("브라질","BRA"),("모로코","MAR"),("프랑스","FRA"),("독일","GER"),
            ("스페인","ESP"),("아르헨티나","ARG"),("잉글랜드","ENG"),("포르투갈","POR"),
            ("일본","JPN"),("한국","KOR"),("대한민국","KOR"),("미국","USA"),
            ("멕시코","MEX"),("네덜란드","NED"),("이탈리아","ITA"),
        ]:
            if name in title:
                if not data.get("team_a"):
                    data["team_a"] = code
                elif not data.get("team_b"):
                    data["team_b"] = code
    else:
        words = title.split()
        data["player"] = " ".join(words[:2]) if words else title

    query = build_query(content_type, data)
    print(f"이미지 검색: {query}")
    image_urls = search_images(query, count=3)

    if not image_urls:
        send_message(
            f"⚠️ 이미지 검색 실패\n\n**{title[:80]}**\n\n"
            "사진을 직접 첨부해주시면 계속 진행할게요."
        )
        sm.save({"status": "awaiting_photo_manual", "content_type": content_type, "story": story})
        return

    msg = send_photo_options(image_urls, title)
    sm.save({
        "status": "awaiting_photo",
        "content_type": content_type,
        "story": story,
        "image_options": image_urls,
        "last_message_id": msg["id"],
    })
    print("Discord 발송 완료.")


if __name__ == "__main__":
    main()
