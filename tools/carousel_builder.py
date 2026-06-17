import re
import asyncio
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "match-result-carousel.html"

TEAM_CODES = {
    # 한글
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
    # 영어
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
        "eyebrow": f"WC \'26 · {date_str}",
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


def extract_transfer_data(headline: str, priority: int = 1) -> dict:
    reliability = {3: "🟢 OFFICIAL", 2: "🟡 LIKELY", 1: "🔴 RUMOUR"}.get(priority, "🔴")
    clean = re.sub(r"[-|·,].*$", "", headline).strip()
    short = clean[:35]
    words = headline.split()
    player = " ".join(words[:2]) if words else headline
    return {
        "team_a": "TRANSFER", "team_b": "NEWS",
        "score_a": "", "score_b": "",
        "eyebrow": f"TRANSFER \'26 · {reliability}",
        "headline_line1": short,
        "headline_line2": reliability,
        "point_01": headline[:50],
        "point_02": "", "point_03": "",
        "view01_title": "이적 상황",
        "view01_text": headline[:200],
        "view02_title": "다음 행방",
        "view02_text": "추후 공식 발표 예정.",
        "next_label": "TRANSFER MARKET",
        "match_a_date": "", "match_a_home": "", "match_a_away": "", "match_a_venue": "",
        "match_b_date": "", "match_b_home": "", "match_b_away": "", "match_b_venue": "",
        "team_a_class": "transfer", "team_b_class": "news",
        "player": player,
    }


def build_html(data: dict, photo_s1: str, photo_s2: str = "", photo_s3: str = "") -> str:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("{{PHOTO_URL_S1}}", photo_s1)
    html = html.replace("{{PHOTO_URL_S2}}", photo_s2 or photo_s1)
    html = html.replace("{{PHOTO_URL_S3}}", photo_s3 or photo_s2 or photo_s1)
    mapping = {
        "{{EYEBROW}}": data.get("eyebrow", ""),
        "{{HEADLINE_LINE1}}": data.get("headline_line1", ""),
        "{{HEADLINE_LINE2}}": data.get("headline_line2", ""),
        "{{TEAM_A}}": data.get("team_a", ""),
        "{{TEAM_B}}": data.get("team_b", ""),
        "{{SCORE_A}}": str(data.get("score_a", "")),
        "{{SCORE_B}}": str(data.get("score_b", "")),
        "{{POINT_01}}": data.get("point_01", ""),
        "{{POINT_02}}": data.get("point_02", ""),
        "{{POINT_03}}": data.get("point_03", ""),
        "{{VIEW01_TITLE}}": data.get("view01_title", ""),
        "{{VIEW01_TEXT}}": data.get("view01_text", ""),
        "{{VIEW02_TITLE}}": data.get("view02_title", ""),
        "{{VIEW02_TEXT}}": data.get("view02_text", ""),
        "{{NEXT_LABEL}}": data.get("next_label", "NEXT MATCH"),
        "{{MATCH_A_DATE}}": data.get("match_a_date", ""),
        "{{MATCH_A_HOME}}": data.get("match_a_home", ""),
        "{{MATCH_A_AWAY}}": data.get("match_a_away", ""),
        "{{MATCH_A_VENUE}}": data.get("match_a_venue", ""),
        "{{MATCH_B_DATE}}": data.get("match_b_date", ""),
        "{{MATCH_B_HOME}}": data.get("match_b_home", ""),
        "{{MATCH_B_AWAY}}": data.get("match_b_away", ""),
        "{{MATCH_B_VENUE}}": data.get("match_b_venue", ""),
        "{{TEAM_A_CLASS}}": data.get("team_a_class", ""),
        "{{TEAM_B_CLASS}}": data.get("team_b_class", ""),
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
