import os
import requests

CLIENT_ID = os.environ["NAVER_CLIENT_ID"]
CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]

HEADERS = {
    "X-Naver-Client-Id": CLIENT_ID,
    "X-Naver-Client-Secret": CLIENT_SECRET,
}

IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def search_images(query, count=3):
    """네이버 이미지 검색 → URL 리스트 (최대 count개)"""
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/image.json",
            headers=HEADERS,
            params={"query": query, "display": min(count + 3, 10),
                    "sort": "sim", "filter": "large"},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        urls = []
        for item in items:
            url = item.get("link", "")
            if url.startswith("http") and any(url.lower().endswith(e) for e in IMG_EXTS):
                urls.append(url)
            if len(urls) >= count:
                break
        return urls
    except Exception as e:
        print(f"[Naver 이미지] 오류: {e}")
        return []


def build_query(content_type, data):
    if content_type == "worldcup":
        ta = data.get("team_a", "")
        tb = data.get("team_b", "")
        return f"{ta} {tb} 2026 월드컵"
    elif content_type == "transfer":
        return f"{data.get('player', '')} 이적 2026 축구"
    return "2026 FIFA 월드컵"
