#!/usr/bin/env python3
"""
OFF90 데일리 파이프라인
뉴스 수집 → 네이버 이미지 검색 → Discord 사진 선택지 발송
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.news_scraper import scrape_news
from tools.naver_image import search_images, build_query
from tools.discord_bot import send_message, send_photo_options
import tools.state_manager as sm


def select_top_story(news: dict):
    wc = [a for a in news.get("worldcup", []) if a.get("priority", 0) >= 3]
    if wc:
        return "worldcup", wc[0]
    tr = [a for a in news.get("transfer", []) if a.get("priority", 0) >= 2]
    if tr:
        return "transfer", tr[0]
    all_news = news.get("worldcup", []) + news.get("transfer", [])
    if all_news:
        kind = "worldcup" if all_news[0] in news.get("worldcup", []) else "transfer"
        return kind, all_news[0]
    return None, None


def main():
    state = sm.load()
    if state.get("status") not in ("idle", "published", None):
        print(f"진행 중인 콘텐츠 있음 (상태: {state['status']}). 건너뜀.")
        return

    print("뉴스 수집 중...")
    news = scrape_news()
    content_type, story = select_top_story(news)

    if not story:
        send_message("⚽ **OFF90**\n\n오늘은 주요 뉴스가 없습니다.")
        return

    title = story.get("title_ko") or story.get("title", "")
    print(f"선택: [{content_type}] {title}")

    data = {}
    if content_type == "worldcup":
        for name, code in [
            ("브라질","BRA"),("모로코","MAR"),("프랑스","FRA"),("독일","GER"),
            ("스페인","ESP"),("아르헨티나","ARG"),("잉글랜드","ENG"),("포르투갈","POR"),
            ("일본","JPN"),("한국","KOR"),("대한민국","KOR"),("미국","USA"),
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
        sm.save({"status": "awaiting_photo_manual",
                 "content_type": content_type, "story": story})
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
