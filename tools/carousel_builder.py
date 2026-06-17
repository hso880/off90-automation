import re
import asyncio
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "match-result-carousel.html"

TEAM_CODES = {
    "브라질": "BRA", "모로코": "MAR", "프랑스": "FRA", "독일": "GER",
    "스페인": "ESP", "아르헨티나": "ARG", "잉글랜드": "ENG", "포르투갈": "POR",
    "일본": "JPN", "한국": "KOR", "대한민국": "KOR", "미국": "USA",
    "멕시코": "MEX", "네덜란드": "NED", "이탈리아": "ITA", "벨기에": "BEL",
    "크로아티아": "CRO", "세네갈": "SEN", "가나": "GHA", "나이지리아": "NGA",
    "코트디부아르": "CIV", "호주": "AUS", "사우디": "KSA", "이란": "IRN",
    "카타르": "QAT", "캐나다": "CAN", "에콰도르": "ECU", "우루과이": "URU",
    "칠레": "CHI", "콜롬비아": "COL", "페루": "PER", "폴란드": "POL",
    "덴마크": "DEN", "스위스": "SUI", "오스트리아": "AUT", "우크라이나": "UKR",
    "튀르키예": "TUR", "슬로바키아": "SVK", "슬로베니아": "SVN",
    "Brazil": "BRA", "Morocco": "MAR", "France": "FRA", "Germany": "GER",
    "Spain": "ESP", "Argentina": "ARG", "England": "ENG", "Portugal": "POR",
    "Japan": "JPN", "South Korea": "KOR", "Korea": "KOR", "USA": "USA",
    "Mexico": "MEX", "Netherlands": "NED", "Italy": "ITA", "Belgium": "BEL",
    "Croatia": "CRO", "Senegal": "SEN", "Ghana": "GHA", "Nigeria": "NGA",
    "Australia": "AUS", "Saudi Arabia": "KSA", "Iran": "IRN", "Qatar": "QAT",
    "Canada": "CAN", "Ecuador": "ECU", "Uruguay": "URU", "Chile": "CHI",
    "Colombia": "COL", "Peru": "PER", "Poland": "POL", "Denmark": "DEN",
    "Switzerland": "SUI", "Austria": "AUT", "Ukraine": "UKR", "Turkey": "TUR",
}

# 주요 클럽명 사전 (원문 → 표준 한글 표기)
CLUBS = {
    "맨유": "맨유", "맨체스터유나이티드": "맨유", "맨체스터 유나이티드": "맨유",
    "Manchester United": "맨유", "Man United": "맨유", "Man Utd": "맨유",
    "맨시티": "맨시티", "맨체스터시티": "맨시티", "맨체스터 시티": "맨시티",
    "Manchester City": "맨시티", "Man City": "맨시티",
    "바르셀로나": "바르셀로나", "Barcelona": "바르셀로나", "Barca": "바르셀로나",
    "레알마드리드": "레알 마드리드", "레알 마드리드": "레알 마드리드",
    "Real Madrid": "레알 마드리드", "Real": "레알 마드리드",
    "PSG": "PSG", "파리생제르맹": "PSG", "Paris Saint-Germain": "PSG",
    "아스날": "아스날", "Arsenal": "아스날",
    "리버풀": "리버풀", "Liverpool": "리버풀",
    "첼시": "첼시", "Chelsea": "첼시",
    "유벤투스": "유벤투스", "Juventus": "유벤투스", "Juve": "유벤투스",
    "바이에른": "바이에른", "Bayern Munich": "바이에른", "Bayern": "바이에른",
    "인터밀란": "인터 밀란", "Inter Milan": "인터 밀란", "Inter": "인터 밀란",
    "AC밀란": "AC밀란", "AC Milan": "AC밀란", "Milan": "AC밀란",
    "아틀레티코": "아틀레티코", "Atletico Madrid": "아틀레티코", "Atletico": "아틀레티코",
    "토트넘": "토트넘", "Tottenham": "토트넘", "Spurs": "토트넘",
    "뉴캐슬": "뉴캐슬", "Newcastle": "뉴캐슬",
    "나폴리": "나폴리", "Napoli": "나폴리",
    "도르트문트": "도르트문트", "Dortmund": "도르트문트", "BVB": "도르트문트",
    "로마": "AS로마", "AS Roma": "AS로마", "Roma": "AS로마",
    "세비야": "세비야", "Sevilla": "세비야",
    "베티스": "베티스", "Real Betis": "베티스",
    "라이프치히": "라이프치히", "RB Leipzig": "라이프치히",
    "플라멩구": "플라멩구", "Flamengo": "플라멩구",
}

TRANSFER_VERBS = ["이적", "합류", "계약", "임대", "복귀", "영입", "방출", "퇴단", "거절", "협상"]


def _find_clubs(text: str) -> list:
    found = []
    for key, val in CLUBS.items():
        if key in text and val not in found:
            found.append(val)
        if len(found) >= 2:
            break
    return found


def extract_worldcup_data(headline: str, pub_date: str = "") -> dict:
    score_m = re.search(r"(\d+)\s*[-:]\s*(\d+)", headline)
    score_a = score_m.group(1) if score_m else "?"
    score_b = score_m.group(2) if score_m else "?"

    team_a_code, team_b_code = "TEAM A", "TEAM B"
    team_a_name, team_b_name = "", ""
    for name, code in TEAM_CODES.items():
        if name in headline:
            if not team_a_name:
                team_a_name, team_a_code = name, code
            elif not team_b_name and name != team_a_name:
                team_b_name, team_b_code = name, code
            if team_a_name and team_b_name:
                break

    clean = re.sub(r"\d+\s*[-:]\s*\d+", "", headline)
    for name in TEAM_CODES:
        clean = clean.replace(name, "")
    clean = re.sub(r"[,·|…\s]+", " ", clean).strip()
    words = clean.split()
    hl1 = " ".join(words[:4]) if words else f"{team_a_code} vs {team_b_code}"
    hl2 = " ".join(words[4:7]) if len(words) > 4 else f"{score_a} : {score_b}"
    date_str = pub_date[:10] if pub_date else "2026"

    return {
        "team_a": team_a_code, "team_b": team_b_code,
        "score_a": score_a, "score_b": score_b,
        "eyebrow": f"WC '26 · {date_str}",
        "headline_line1": hl1,
        "headline_line2": hl2,
        "point_01": f"{team_a_code} 승리 · {score_a}-{score_b}",
        "point_02": "주요 장면 하이라이트",
        "point_03": "경기 총평",
        "view01_title": "경기 흐름",
        "view01_text": headline[:120],
        "view02_title": "핵심 포인트",
        "view02_text": f"{team_a_code}와 {team_b_code}의 다음 경기가 주목된다.",
        "next_label": "NEXT MATCH",
        "match_a_date": "TBD", "match_a_home": team_a_code,
        "match_a_away": "TBD", "match_a_venue": "Stadium TBD",
        "match_b_date": "TBD", "match_b_home": team_b_code,
        "match_b_away": "TBD", "match_b_venue": "Stadium TBD",
        "team_a_class": team_a_code.lower()[:3],
        "team_b_class": team_b_code.lower()[:3],
    }


def extract_transfer_data(headline: str, pub_date: str = "", priority: int = 1) -> dict:
    rel_full  = {3: "🟢 OFFICIAL", 2: "🟡 LIKELY", 1: "🔴 RUMOUR"}.get(priority, "🔴 RUMOUR")
    rel_short = {3: "OFFICIAL",    2: "LIKELY",    1: "RUMOUR"}.get(priority, "RUMOUR")

    # ── 선수명 추출 ──────────────────────────────────────────
    # 형식: "선수명, 클럽 이적..." 또는 "선수명 이적..." 
    player_m = re.match(r"^([가-힣A-Za-z][가-힣A-Za-z\s\.]{1,18}?)[,·\s]", headline)
    player = player_m.group(1).strip() if player_m else headline.split()[0]

    # ── 클럽명 추출 ─────────────────────────────────────────
    clubs = _find_clubs(headline)
    from_club = clubs[0] if clubs else ""
    to_club   = clubs[1] if len(clubs) > 1 else ""

    # ── 이적 동사 파악 ───────────────────────────────────────
    action = next((v for v in TRANSFER_VERBS if v in headline), "이적설")

    # ── 슬라이드 텍스트 ──────────────────────────────────────
    if to_club:
        view01_title = f"{player}, {to_club} {action}"[:28]
        view02_title = f"{to_club} 이적 배경"[:20]
        view02_text  = (f"{player}가 {from_club or '현 소속팀'}을(를) 떠나 {to_club}으로 "
                        f"{action}하는 방향으로 논의 중이다. 신뢰도: {rel_full}")
    elif from_club:
        view01_title = f"{player}, {from_club} 출발"[:28]
        view02_title = f"{player} 다음 행방"[:20]
        view02_text  = f"{player}의 {from_club} 이탈 후 행선지가 주목된다. 신뢰도: {rel_full}"
    else:
        view01_title = f"{player} 이적 상황"[:28]
        view02_title = "이적 시장 전망"
        view02_text  = f"신뢰도: {rel_full}\n{player}의 이적 행보에 관심이 쏠리고 있다."

    date_str = pub_date[:10] if pub_date else "2026"

    return {
        # 슬라이드 1 헤드라인
        "team_a": "TRANSFER", "team_b": rel_short,
        "score_a": "", "score_b": "",
        "eyebrow": f"TRANSFER '26 · {rel_full}",
        "headline_line1": player,
        "headline_line2": f"→ {to_club}" if to_club else action,
        "point_01": headline[:50],
        "point_02": f"From · {from_club}" if from_club else "",
        "point_03": f"To · {to_club}"     if to_club   else "",
        # 슬라이드 2·3 (VER B)
        "view01_title": view01_title,
        "view01_text":  headline[:200],
        "view02_title": view02_title,
        "view02_text":  view02_text,
        # 슬라이드 4 — 이적 상태 패널로 재활용
        "next_label":    "TRANSFER STATUS",
        "match_a_date":  rel_full,
        "match_a_home":  player,
        "match_a_away":  from_club or "현 소속팀",
        "match_a_venue": f"→ {to_club}" if to_club else "행선지 미정",
        "match_b_date":  date_str,
        "match_b_home":  "출처",
        "match_b_away":  "Fabrizio Romano / 공식",
        "match_b_venue": "이적 시장 정보",
        "team_a_class": "transfer",
        "team_b_class": "news",
        # 사진 쿼리용 메타
        "player":     player,
        "club":       to_club or from_club,
        "from_club":  from_club,
        "to_club":    to_club,
        "action":     action,
    }


def build_html(data: dict, photo_s1: str, photo_s2: str = "", photo_s3: str = "") -> str:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("{{PHOTO_URL_S1}}", photo_s1)
    html = html.replace("{{PHOTO_URL_S2}}", photo_s2 or photo_s1)
    html = html.replace("{{PHOTO_URL_S3}}", photo_s3 or photo_s2 or photo_s1)
    mapping = {
        "{{EYEBROW}}":       data.get("eyebrow", ""),
        "{{HEADLINE_LINE1}}": data.get("headline_line1", ""),
        "{{HEADLINE_LINE2}}": data.get("headline_line2", ""),
        "{{TEAM_A}}":        data.get("team_a", ""),
        "{{TEAM_B}}":        data.get("team_b", ""),
        "{{SCORE_A}}":       str(data.get("score_a", "")),
        "{{SCORE_B}}":       str(data.get("score_b", "")),
        "{{POINT_01}}":      data.get("point_01", ""),
        "{{POINT_02}}":      data.get("point_02", ""),
        "{{POINT_03}}":      data.get("point_03", ""),
        "{{VIEW01_TITLE}}":  data.get("view01_title", ""),
        "{{VIEW01_TEXT}}":   data.get("view01_text", ""),
        "{{VIEW02_TITLE}}":  data.get("view02_title", ""),
        "{{VIEW02_TEXT}}":   data.get("view02_text", ""),
        "{{NEXT_LABEL}}":    data.get("next_label", "NEXT MATCH"),
        "{{MATCH_A_DATE}}":  data.get("match_a_date", ""),
        "{{MATCH_A_HOME}}":  data.get("match_a_home", ""),
        "{{MATCH_A_AWAY}}":  data.get("match_a_away", ""),
        "{{MATCH_A_VENUE}}": data.get("match_a_venue", ""),
        "{{MATCH_B_DATE}}":  data.get("match_b_date", ""),
        "{{MATCH_B_HOME}}":  data.get("match_b_home", ""),
        "{{MATCH_B_AWAY}}":  data.get("match_b_away", ""),
        "{{MATCH_B_VENUE}}": data.get("match_b_venue", ""),
        "{{TEAM_A_CLASS}}":  data.get("team_a_class", ""),
        "{{TEAM_B_CLASS}}":  data.get("team_b_class", ""),
    }
    for k, v in mapping.items():
        html = html.replace(k, str(v))
    return html


async def _render_async(html_content: str, out_dir: Path) -> list:
    from playwright.async_api import async_playwright
    html_path = out_dir / "carousel.html"
    html_path.write_text(html_content, encoding="utf-8")

    pngs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 900, "height": 700})
        await page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        frame = page.locator(".ig-frame")
        for i in range(4):
            path = out_dir / f"slide_{i+1:02d}.png"
            await frame.screenshot(path=str(path))
            pngs.append(path)
            if i < 3:
                await page.locator("button", has_text="▶").click()
                await page.wait_for_timeout(600)

        await browser.close()
    return pngs


def render(html_content: str, out_dir: Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_render_async(html_content, out_dir))
