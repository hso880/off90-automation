#!/usr/bin/env python3
"""
GitHub Actions 실행: 뉴스 수집 → 카카오톡 나에게 보내기
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__) or ".")

from tools.news_scraper import scrape_news, format_kakao_message
from tools.kakao_send_me import send_me


def main():
    print("뉴스 수집 중...")
    news = scrape_news()

    wc_count = len(news.get("worldcup", []))
    tr_count = len(news.get("transfer", []))
    print(f"월드컵 {wc_count}개 / 이적시장 {tr_count}개 수집 완료")

    if wc_count + tr_count == 0:
        print("수집된 뉴스가 없습니다. 종료.")
        sys.exit(0)

    message = format_kakao_message(news)
    print("\n발송 내용:\n" + "-" * 40)
    print(message)
    print("-" * 40)

    send_me(message)
    print("완료")


if __name__ == "__main__":
    main()
