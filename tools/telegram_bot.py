import json
import os
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BASE = f"https://api.telegram.org/bot{TOKEN}"


def _post(method, data=None, files=None):
    if files:
        return requests.post(f"{BASE}/{method}", data=data, files=files).json()
    return requests.post(f"{BASE}/{method}", json=data).json()


def send_message(text, reply_markup=None):
    d = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        d["reply_markup"] = reply_markup
    return _post("sendMessage", d)


def send_photo_url(photo_url, caption="", reply_markup=None):
    d = {"chat_id": CHAT_ID, "photo": photo_url, "caption": caption}
    if reply_markup:
        d["reply_markup"] = reply_markup
    return _post("sendPhoto", d)


def send_media_group_urls(urls, captions=None):
    """최대 10장 사진 그룹 발송 (URL 기반)"""
    media = []
    for i, url in enumerate(urls):
        item = {"type": "photo", "media": url}
        if captions and i < len(captions):
            item["caption"] = captions[i]
        media.append(item)
    return _post("sendMediaGroup", {"chat_id": CHAT_ID, "media": media})


def send_photo_options(image_urls, news_title):
    """3장 사진 선택지 + 인라인 버튼"""
    captions = ["① 1번", "② 2번", "③ 3번"]
    send_media_group_urls(image_urls[:3], captions)
    markup = {
        "inline_keyboard": [[
            {"text": "① 1번", "callback_data": "photo_1"},
            {"text": "② 2번", "callback_data": "photo_2"},
            {"text": "③ 3번", "callback_data": "photo_3"},
        ]]
    }
    send_message(f"<b>{news_title[:80]}</b>\n\n위 사진 중 하나를 골라주세요:", markup)


def send_carousel_preview(slide_paths, draft_caption):
    """슬라이드 4장 파일 전송 + 초안 캡션"""
    data = {"chat_id": CHAT_ID}
    media = []
    files = {}
    for i, path in enumerate(slide_paths):
        key = f"s{i}"
        media.append({"type": "photo", "media": f"attach://{key}"})
        files[key] = open(str(path), "rb")
    data["media"] = json.dumps(media)
    requests.post(f"{BASE}/sendMediaGroup", data=data, files=files)
    for f in files.values():
        f.close()

    send_message(
        f"캐러셀 완성\n\n✏️ 초안 캡션:\n\n{draft_caption}\n\n"
        "───────\n"
        "캡션을 수정하려면 직접 입력해주세요.\n"
        "그대로 쓰려면 <b>발행해줘</b> 라고 보내주세요."
    )


def get_updates(offset=None):
    params = {"timeout": 0, "limit": 20}
    if offset is not None:
        params["offset"] = offset
    return requests.get(f"{BASE}/getUpdates", params=params).json()


def answer_callback(callback_query_id, text="✅"):
    _post("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
