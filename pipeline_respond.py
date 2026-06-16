#!/usr/bin/env python3
"""
텔레그램 폴링 응답기 (5분마다 실행)
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.telegram_bot import get_updates, answer_callback, send_message, send_carousel_preview
import tools.state_manager as sm

PUBLISH_KW = {"발행해줘", "발행", "승인", "올려줘", "게시해줘", "올려"}


def handle_photo_selection(choice: int, state: dict):
    urls = state.get("image_options", [])
    if not (1 <= choice <= len(urls)):
        send_message("1~3 중에서 선택해주세요.")
        return

    selected_url = urls[choice - 1]
    content_type = state.get("content_type", "worldcup")
    story = state.get("story", {})
    title = story.get("title_ko") or story.get("title", "")

    send_message("🎨 캐러셀 생성 중... (약 60초 소요)")

    from tools.carousel_builder import extract_worldcup_data, extract_transfer_data, build_html, render

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
            return

        from tools.ig_publisher import upload_to_cloudinary
        cloudinary_urls = []
        for p in slide_paths:
            try:
                url = upload_to_cloudinary(p)
                cloudinary_urls.append(url)
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

        sm.save({
            "status": "awaiting_publish",
            "content_type": content_type,
            "story": story,
            "selected_image": selected_url,
            "cloudinary_urls": cloudinary_urls,
            "pending_caption": draft,
        })

        send_carousel_preview(slide_paths, draft)


def handle_publish(state: dict, caption: str = None):
    urls = state.get("cloudinary_urls", [])
    if not urls:
        send_message("발행할 콘텐츠가 없습니다. 처음부터 다시 시작해주세요.")
        sm.clear()
        return

    final_caption = caption or state.get("pending_caption", "")
    send_message("📤 Instagram 발행 중...")

    try:
        from tools.ig_publisher import publish_carousel
        media_id = publish_carousel(urls, final_caption)
        send_message(f"✅ 업로드 완료!\n\nhttps://www.instagram.com/p/{media_id}/")
        sm.save({"status": "published"})
    except Exception as e:
        send_message(f"❌ 발행 실패: {e}")


def main():
    offset = sm.load_offset()
    result = get_updates(offset)
    updates = result.get("result", [])

    if not updates:
        return

    state = sm.load()
    last_id = None

    for update in updates:
        last_id = update["id"]

        # 인라인 버튼 콜백
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_data = cb.get("data", "")
            answer_callback(cb["id"])

            if cb_data.startswith("photo_") and state.get("status") == "awaiting_photo":
                try:
                    choice = int(cb_data.split("_")[1])
                    handle_photo_selection(choice, state)
                    state = sm.load()
                except (ValueError, IndexError):
                    pass
            continue

        # 일반 텍스트
        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        if not text:
            continue

        status = state.get("status", "idle")

        if any(kw in text for kw in PUBLISH_KW):
            if status == "awaiting_publish":
                handle_publish(state)
                state = sm.load()
            else:
                send_message("발행할 콘텐츠가 없습니다. 먼저 뉴스 사진을 선택해주세요.")

        elif status == "awaiting_publish" and len(text) > 8 and not text.startswith("/"):
            # 사용자 캡션 입력
            updated = {**state, "pending_caption": text}
            sm.save(updated)
            state = updated
            send_message(
                f"✅ 캡션 저장됨:\n\n{text}\n\n"
                "<b>발행해줘</b> 라고 보내면 Instagram에 올려드릴게요."
            )

        elif text.lower() in ("/start", "/help", "도움말"):
            send_message(
                "⚽ <b>OFF90 자동화 봇</b>\n\n"
                "매일 뉴스 + 사진 선택지를 보내드립니다.\n\n"
                "① 사진 번호 선택 → 캐러셀 생성\n"
                "② 캡션 수정 입력 (선택)\n"
                "③ <b>발행해줘</b> → Instagram 자동 업로드"
            )

    if last_id is not None:
        sm.save_offset(last_id)


if __name__ == "__main__":
    main()
