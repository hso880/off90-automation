#!/usr/bin/env python3
"""
Discord 폴링 응답기 (5분마다 실행)
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.discord_bot import get_recent_messages, send_message, send_carousel_preview
import tools.state_manager as sm

PUBLISH_KW = {"발행해줘", "발행", "승인", "올려줘", "게시해줘", "올려"}
BOT_TOKEN  = os.environ["DISCORD_BOT_TOKEN"]


def _bot_id():
    import requests
    r = requests.get("https://discord.com/api/v10/users/@me",
                     headers={"Authorization": f"Bot {BOT_TOKEN}"})
    return r.json().get("id", "")


def get_new_user_messages(last_msg_id: str) -> list:
    """last_msg_id 이후의 사용자 메시지 (오래된 순)"""
    msgs = get_recent_messages(50)
    bot_id = _bot_id()
    result = []
    for m in reversed(msgs):        # Discord API는 최신순 → 뒤집어 오래된 순으로
        if int(m["id"]) <= int(last_msg_id or "0"):
            continue
        if m["author"].get("bot") or m["author"]["id"] == bot_id:
            continue
        result.append(m)
    return result


def handle_photo_selection(choice: int, state: dict):
    urls = state.get("image_options", [])
    if not (1 <= choice <= len(urls)):
        send_message("1~3 중에서 입력해주세요.")
        return

    selected_url = urls[choice - 1]
    content_type = state.get("content_type", "worldcup")
    story = state.get("story", {})
    title = story.get("title_ko") or story.get("title", "")

    msg = send_message("🎨 캐러셀 생성 중... (약 60초 소요)")
    sm.save({**state,
             "status": "generating",
             "last_message_id": msg["id"]})

    from tools.carousel_builder import (
        extract_worldcup_data, extract_transfer_data, build_html, render
    )

    if content_type == "worldcup":
        data = extract_worldcup_data(title, story.get("published", ""))
    else:
        data = extract_transfer_data(title, story.get("priority", 1))

    html = build_html(data, selected_url)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        slide_paths = render(html, tmp_path)

        if not slide_paths:
            send_message("캐러셀 생성 실패. 다시 시도해주세요.")
            sm.save({**state, "status": "awaiting_photo"})
            return

        from tools.ig_publisher import upload_to_cloudinary
        cloudinary_urls = []
        for p in slide_paths:
            try:
                cloudinary_urls.append(upload_to_cloudinary(p))
            except Exception as e:
                print(f"  Cloudinary 업로드 실패: {e}")

        if content_type == "worldcup":
            ta = data.get("team_a", "")
            tb = data.get("team_b", "")
            sa = data.get("score_a", "")
            sb = data.get("score_b", "")
            draft = (
                f"{ta} {sa}-{sb} {tb}\n\n"
                f"{story.get('title_ko', title)}\n\n"
                f"#월드컵2026 #{ta.lower()} #{tb.lower()} #2026월드컵 #FIFA월드컵 #off90"
            )
        else:
            draft = (
                f"{story.get('title_ko', title)}\n\n"
                f"#이적시장 #해외축구 #2026이적 #축구 #off90"
            )

        preview_msg = send_carousel_preview(slide_paths, draft)

    sm.save({
        "status": "awaiting_publish",
        "content_type": content_type,
        "story": story,
        "selected_image": selected_url,
        "cloudinary_urls": cloudinary_urls,
        "pending_caption": draft,
        "last_message_id": preview_msg["id"],
    })


def handle_publish(state: dict, caption: str = None):
    urls = state.get("cloudinary_urls", [])
    if not urls:
        send_message("발행할 콘텐츠가 없습니다. 처음부터 다시 시작해주세요.")
        sm.clear()
        return

    final_caption = caption or state.get("pending_caption", "")
    msg = send_message("📤 Instagram 발행 중...")
    sm.save({**state, "last_message_id": msg["id"]})

    try:
        from tools.ig_publisher import publish_carousel
        media_id = publish_carousel(urls, final_caption)
        send_message(f"✅ 업로드 완료!\nhttps://www.instagram.com/p/{media_id}/")
        sm.save({"status": "published"})
    except Exception as e:
        send_message(f"❌ 발행 실패: {e}")


def main():
    state = sm.load()
    last_msg_id = state.get("last_message_id", "0")
    status = state.get("status", "idle")

    if status == "generating":
        # 캐러셀 생성 중 → 무시
        return

    new_msgs = get_new_user_messages(last_msg_id)
    if not new_msgs:
        return

    for msg in new_msgs:
        text = msg.get("content", "").strip()
        if not text:
            continue

        # last_message_id 업데이트
        sm.save({**state, "last_message_id": msg["id"]})
        state = sm.load()
        status = state.get("status", "idle")

        # 사진 선택 (숫자 입력)
        if status == "awaiting_photo" and text in ("1", "2", "3"):
            handle_photo_selection(int(text), state)
            state = sm.load()

        # 발행 명령
        elif any(kw in text for kw in PUBLISH_KW):
            if status == "awaiting_publish":
                handle_publish(state)
                state = sm.load()
            else:
                send_message("발행할 콘텐츠가 없습니다. 먼저 뉴스 사진 번호를 선택해주세요.")

        # 캡션 수정
        elif status == "awaiting_publish" and len(text) > 5 and not text.startswith("/"):
            updated = {**state, "pending_caption": text}
            sm.save(updated)
            state = updated
            send_message(
                f"✅ 캡션 저장됨:\n\n{text}\n\n**발행해줘** 라고 입력하면 Instagram에 올려드릴게요."
            )

        elif text.lower() in ("/help", "도움말"):
            send_message(
                "⚽ **OFF90 자동화 봇**\n\n"
                "① 뉴스 사진 번호 입력 (1/2/3)\n"
                "② 캡션 수정 입력 (선택사항)\n"
                "③ **발행해줘** → Instagram 자동 업로드"
            )


if __name__ == "__main__":
    main()
