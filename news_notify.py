#!/usr/bin/env python3
"""
GitHub Actions 실행: 월드컵 뉴스 수집 → 카카오톡 나에게 보내기
"""
import sys
import os

# GitHub Actions에서는 repo root 기준으로 실행됨
sys.path.insert(0, os.path.dirname(__file__))

from tools.news_scraper import scrape_news, format_kakao_message
from tools.kakao_send_me import send_me


def main():
    print("뉴스 수집 중...")
    articles = scrape_news(max_per_feed=5, total_max=8)

    if not articles:
        print("수집된 뉴스가 없습니다. 종료.")
        sys.exit(0)

    print(f"{len(articles)}개 기사 수집 완료")
    message = format_kakao_message(articles)
    print("\n발송 내용:\n" + "-" * 40)
    print(message)
    print("-" * 40)

    send_me(message)
    print("완료")


if __name__ == "__main__":
    main()
