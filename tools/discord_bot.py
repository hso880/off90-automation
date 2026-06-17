import json, os
import requests

TOKEN      = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"]
BASE       = "https://discord.com/api/v10"
HDR        = {"Authorization": f"Bot {TOKEN}"}


def send_message(text: str) -> dict:
    r = requests.post(f"{BASE}/channels/{CHANNEL_ID}/messages",
                      headers=HDR, json={"content": text})
    r.raise_for_status()
    return r.json()


def send_photo_confirm(photos: dict, story_title: str) -> dict:
    """슬라이드1·2·3 자동 선택 사진 → Discord 확인 요청"""
    labels = {"s1": "슬라이드 1 (메인)", "s2": "슬라이드 2 (View 01)", "s3": "슬라이드 3 (View 02)"}
    embeds = []
    for key in ("s1", "s2", "s3"):
        url = photos.get(key, "")
        if url:
            embeds.append({
                "title": labels[key],
                "image": {"url": url},
                "color": 0x00873E,
            })
    payload = {
        "content": (
            f"**{story_title[:80]}**\n\n"
            "자동으로 고른 사진들이에요 👆\n\n"
            "**OK** — 이대로 제작 시작\n"
            "**다시** — 사진 전체 새로 검색\n"
            "**1번 바꿔** / **2번 바꿔** / **3번 바꿔** — 해당 슬라이드 사진만 교체"
        ),
        "embeds": embeds,
    }
    r = requests.post(f"{BASE}/channels/{CHANNEL_ID}/messages", headers=HDR, json=payload)
    r.raise_for_status()
    return r.json()


def send_carousel_preview(slide_paths: list, draft_caption: str) -> dict:
    """슬라이드 4장 + 초안 캡션 발송"""
    from pathlib import Path
    files = {}
    for i, path in enumerate(slide_paths):
        files[f"files[{i}]"] = (Path(path).name, open(str(path), "rb"), "image/png")

    content = (
        f"캐러셀 완성! 👇\n\n"
        f"✏️ 초안 캡션:\n\n{draft_caption}\n\n"
        "───\n"
        "캡션 수정하려면 직접 입력, 그대로면 **발행해줘**"
    )
    r = requests.post(
        f"{BASE}/channels/{CHANNEL_ID}/messages",
        headers=HDR,
        data={"payload_json": json.dumps({"content": content})},
        files=files,
    )
    for f in files.values():
        f[1].close()
    r.raise_for_status()
    return r.json()


def get_recent_messages(limit: int = 50) -> list:
    r = requests.get(f"{BASE}/channels/{CHANNEL_ID}/messages",
                     headers=HDR, params={"limit": limit})
    r.raise_for_status()
    return r.json()
