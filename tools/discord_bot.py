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


def send_photo_options(image_urls: list, news_title: str) -> dict:
    """3장 사진을 임베드로 한 메시지에 발송"""
    embeds = []
    for i, url in enumerate(image_urls[:3], 1):
        embeds.append({
            "title": f"{i}번",
            "image": {"url": url},
            "color": 0x00873E,
        })
    payload = {
        "content": f"**{news_title[:120]}**\n\n사진을 골라주세요. **1**, **2**, **3** 중 하나를 입력하세요:",
        "embeds": embeds,
    }
    r = requests.post(f"{BASE}/channels/{CHANNEL_ID}/messages",
                      headers=HDR, json=payload)
    r.raise_for_status()
    return r.json()


def send_carousel_preview(slide_paths: list, draft_caption: str) -> dict:
    """슬라이드 4장 + 초안 캡션 발송"""
    from pathlib import Path
    files = {}
    for i, path in enumerate(slide_paths):
        files[f"files[{i}]"] = (Path(path).name, open(str(path), "rb"), "image/png")

    content = (
        f"캐러셀 완성!\n\n"
        f"✏️ 초안 캡션:\n\n{draft_caption}\n\n"
        "───\n"
        "캡션을 수정하려면 직접 입력해주세요.\n"
        "그대로 쓰려면 **발행해줘** 라고 입력해주세요."
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
    """최근 메시지 가져오기 (최신순)"""
    r = requests.get(f"{BASE}/channels/{CHANNEL_ID}/messages",
                     headers=HDR, params={"limit": limit})
    r.raise_for_status()
    return r.json()
