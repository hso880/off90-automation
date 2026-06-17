import os
import requests

CLIENT_ID     = os.environ["NAVER_CLIENT_ID"]
CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
HEADERS = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")

KEY_PLAYERS = {
    "FRA": "음바페", "ARG": "메시", "BRA": "비니시우스", "ENG": "벨링엄",
    "ESP": "야말", "POR": "호날두", "GER": "무시알라", "NED": "판다이크",
    "ITA": "키에사", "BEL": "루카쿠", "CRO": "모드리치", "URU": "누녜스",
    "USA": "풀리식", "MEX": "히메네스", "JPN": "도안", "KOR": "손흥민",
    "MAR": "부팔", "SEN": "디아", "NGA": "오시메엔", "GHA": "쿠두스",
    "AUS": "흐루스틱", "KSA": "알다우사리", "IRN": "타레미", "QAT": "알모에즈",
    "POL": "레반도프스키", "DEN": "에릭센", "SUI": "샤키리", "AUT": "아르나우토비치",
}


def search_images(query: str, count: int = 3) -> list:
    """네이버 이미지 검색 → URL 리스트"""
    try:
        r = requests.get(
            "https://openapi.naver.com/v1/search/image.json",
            headers=HEADERS,
            params={"query": query, "display": min(count + 4, 10),
                    "sort": "sim", "filter": "large"},
            timeout=10,
        )
        r.raise_for_status()
        urls = []
        for item in r.json().get("items", []):
            url = item.get("link", "")
            if (url.startswith("http")
                    and any(url.lower().endswith(e) for e in IMG_EXTS)
                    and "logo" not in url.lower()
                    and "icon" not in url.lower()):
                urls.append(url)
            if len(urls) >= count:
                break
        return urls
    except Exception as e:
        print(f"[Naver] 오류: {e}")
        return []


def slide1_queries(content_type: str, data: dict) -> list:
    """슬라이드 1용 쿼리 3개 (사용자 선택용)"""
    if content_type == "worldcup":
        ta, tb = data.get("team_a", ""), data.get("team_b", "")
        pa = KEY_PLAYERS.get(ta, ta)
        pb = KEY_PLAYERS.get(tb, tb)
        return [
            f"{pa} {pb} 2026 월드컵",
            f"{pa} 2026 FIFA 월드컵 경기",
            f"{ta} {tb} 2026 월드컵 선수",
        ]
    else:  # transfer
        player   = data.get("player", "")
        to_club  = data.get("to_club", "")
        from_club = data.get("from_club", "")
        club = to_club or from_club
        return [
            f"{player} {club} 2026" if club else f"{player} 2026 축구",
            f"{player} 이적 2026 축구",
            f"{player} 축구 선수",
        ]


def slide2_query(content_type: str, data: dict) -> str:
    """슬라이드 2용 쿼리 (View01 — 이적 현황 또는 경기 흐름)"""
    if content_type == "worldcup":
        ta = data.get("team_a", "")
        pa = KEY_PLAYERS.get(ta, ta)
        view_title = data.get("view01_title", "")
        return f"{pa} 2026 월드컵 {view_title[:12]}"
    else:
        player    = data.get("player", "")
        from_club = data.get("from_club", "")
        return f"{player} {from_club} 2026" if from_club else f"{player} 이적 2026"


def slide3_query(content_type: str, data: dict) -> str:
    """슬라이드 3용 쿼리 (View02 — 핵심 포인트 또는 다음 행방)"""
    if content_type == "worldcup":
        tb = data.get("team_b", "")
        pb = KEY_PLAYERS.get(tb, tb)
        view_title = data.get("view02_title", "")
        return f"{pb} 2026 월드컵 {view_title[:12]}"
    else:
        player  = data.get("player", "")
        to_club = data.get("to_club", "")
        return f"{player} {to_club} 2026" if to_club else f"{player} 이적시장 2026"
