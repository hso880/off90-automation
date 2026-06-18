#!/usr/bin/env python3
"""
Discord 폴링 응답기 (5분마다 실행)

상태 흐름:
  awaiting_story_selection → (번호) → awaiting_photo_upload
  awaiting_photo_upload    → (이미지 3장) → generating → awaiting_publish
  awaiting_publish         → (발행해줘) → published
"""
import os, sys, tempfile, re
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
    msgs = get_recent_messages(50)
    bot_id = _bot_id()
    result = []
    for m in reversed(msgs):
        if int(m["id"]) <= int(last_msg_id or "0"):
            continue
        if m["author"].get("bot") or m["author"]["id"] == bot_id:
            continue
        result.append(m)
    return result


def _extract_image_urls(msg: dict) -> list:
    """메시지에서 이미지 URL 추출 (attachment + embed)"""
    urls = []
    for att in msg.get("attachments", []):
        ct = att.get("content_type", "")
        if ct.startswith("image/") or att.get("url", "").lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            urls.append(att["url"])
    return urls


def handle_story_selection(choice: int, state: dict):
    """번호 선택 → 사진 업로드 요청"""
    news_list = state.get("news_list", {})
    item = news_list.get(str(choice))
    if not item:
        send_message(f"1~{len(news_list)} 사이의 번호를 입력해주세요.")
        return

    content_type, story = item[0], item[1]
    title = story.get("title_ko") or story.get("title", "")

    from tools.carousel_builder import extract_worldcup_data, extract_transfer_data
    if content_type == "worldcup":
        data = extract_worldcup_data(title, story.get("published", ""))
    else:
        data = extract_transfer_data(title, story.get("published", ""), story.get("priority", 1))

    msg = send_message(
        f"✅ **{title[:70]}**\n\n"
        "사진 3장을 이 채널에 업로드해주세요:\n\n"
        "📸 **1번 사진** — 슬라이드 1 메인 (선수/경기 장면)\n"
        "📸 **2번 사진** — 슬라이드 2 (View 01 관련)\n"
        "📸 **3번 사진** — 슬라이드 3 (View 02 관련)\n\n"
        "한 번에 3장 또는 1장씩 따로 보내도 됩니다.\n"
        "**취소** 로 다시 번호 선택으로 돌아갑니다."
    )

    sm.save({
        "status": "awaiting_photo_upload",
        "content_type": content_type,
        "story": story,
        "extracted_data": data,
        "uploaded_photos": [],
        "last_message_id": msg["id"],
    })


def handle_photo_upload(msg: dict, state: dict):
    """이미지 업로드 처리 — 3장 모이면 자동 제작"""
    imgs = _extract_image_urls(msg)
    if not imgs:
        return  # 이미지 없는 메시지는 무시

    uploaded = list(state.get("uploaded_photos", []))
    uploaded += imgs

    title = (state.get("story", {}).get("title_ko")
             or state.get("story", {}).get("title", ""))

    remaining = 3 - len(uploaded)

    if remaining > 0:
        # 아직 부족
        reply_msg = send_message(
            f"📸 {len(uploaded)}장 받았습니다. 앞으로 **{remaining}장** 더 보내주세요."
        )
        sm.save({**state,
                 "uploaded_photos": uploaded,
                 "last_message_id": reply_msg["id"]})
        return

    # 3장 이상 — 앞 3장만 사용
    photos = {"s1": uploaded[0], "s2": uploaded[1], "s3": uploaded[2]}
    _build_and_preview(state, state.get("extracted_data", {}), photos)


def _build_and_preview(state: dict, data: dict, photos: dict):
    """캐러셀 빌드 → Cloudinary 업로드 → Discord 미리보기"""
    content_type = state.get("content_type", "worldcup")
    story = state.get("story", {})
    title = story.get("title_ko") or story.get("title", "")

    msg = send_message("🎨 캐러셀 제작 중... (약 60초 소요)")
    sm.save({**state, "status": "generating", "last_message_id": msg["id"]})

    from tools.carousel_builder import build_html, render
    html = build_html(data, photos.get("s1", ""), photos.get("s2", ""), photos.get("s3", ""))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        slide_paths = render(html, tmp_path)

        if not slide_paths:
            send_message("❌ 캐러셀 생성 실패. 다시 번호를 입력해주세요.")
            sm.save({**state, "status": "awaiting_story_selection"})
            return

        from tools.ig_publisher import upload_to_cloudinary
        cloudinary_urls = []
        for p in slide_paths:
            try:
                cloudinary_urls.append(upload_to_cloudinary(p))
            except Exception as e:
                print(f"Cloudinary 오류: {e}")

        if content_type == "worldcup":
            ta = data.get("team_a", "")
            tb = data.get("team_b", "")
            sa, sb = data.get("score_a", ""), data.get("score_b", "")
            draft = (
                f"{ta} {sa}-{sb} {tb}\n\n{title}\n\n"
                f"#월드컵2026 #{ta.lower()} #{tb.lower()} #2026월드컵 #FIFA월드컵 #off90"
            )
        else:
            player = data.get("player", "").replace(" ", "")
            club = (data.get("to_club") or data.get("from_club", "")).replace(" ", "")
            draft = (
                f"{title}\n\n"
                f"#이적시장 #해외축구 #2026이적 #{player} #{club or '축구'} #off90"
            )

        preview_msg = send_carousel_preview(slide_paths, draft)

    sm.save({
        "status": "awaiting_publish",
        "content_type": content_type,
        "story": story,
        "cloudinary_urls": cloudinary_urls,
        "pending_caption": draft,
        "last_message_id": preview_msg["id"],
    })


def handle_publish(state: dict):
    urls = state.get("cloudinary_urls", [])
    if not urls:
        send_message("발행할 콘텐츠가 없습니다. 처음부터 다시 시작해주세요.")
        sm.clear()
        return

    final_caption = state.get("pending_caption", "")
    msg = send_message("📤 Instagram 발행 중...")
    sm.save({**state, "last_message_id": msg["id"]})

    try:
        from tools.ig_publisher import publish_carousel
        media_id = publish_carousel(urls, final_caption)
        send_message(f"✅ 업로드 완료!\nhttps://www.instagram.com/p/{media_id}/")
        sm.clear()
    except Exception as e:
        send_message(f"❌ 발행 실패: {e}")


def main():
    state = sm.load()
    last_msg_id = state.get("last_message_id", "0")
    status = state.get("status", "idle")

    if status == "generating":
        return

    new_msgs = get_new_user_messages(last_msg_id)
    if not new_msgs:
        return

    for msg in new_msgs:
        text = msg.get("content", "").strip()

        sm.save({**state, "last_message_id": msg["id"]})
        state = sm.load()
        status = state.get("status", "idle")

        # 취소 — 어느 상태에서든
        if text in ("취소", "/취소", "cancel"):
            sm.save({"status": "awaiting_story_selection",
                     "news_list": state.get("news_list", {}),
                     "last_message_id": msg["id"]})
            send_message("↩️ 취소됐습니다. 번호를 다시 입력해주세요.")
            state = sm.load()
            continue

        # 도움말
        if text.lower() in ("/help", "도움말"):
            send_message(
                "⚽ **OFF90 자동화 봇**\n\n"
                "① 뉴스 번호 입력\n"
                "② 사진 3장 업로드 (슬라이드1·2·3)\n"
                "③ 캐러셀 자동 제작 (~60초)\n"
                "④ (선택) 캡션 수정 후 전송\n"
                "⑤ **발행해줘** → Instagram 업로드\n\n"
                "**취소** 로 번호 선택으로 돌아갑니다."
            )
            continue

        # 1. 뉴스 번호 선택
        _num_m = re.search(r'\d+', text)
        if status == "awaiting_story_selection" and _num_m:
            handle_story_selection(int(_num_m.group()), state)
            state = sm.load()

        # 2. 사진 업로드
        elif status == "awaiting_photo_upload":
            if _extract_image_urls(msg):
                handle_photo_upload(msg, state)
                state = sm.load()
            elif text:
                # 텍스트만 온 경우 안내
                send_message("📸 이미지 파일을 업로드해주세요. (텍스트 메시지는 인식 안 됩니다)")

        # 3. 발행 명령
        elif any(kw in text for kw in PUBLISH_KW):
            if status == "awaiting_publish":
                handle_publish(state)
                state = sm.load()
            else:
                send_message("발행할 콘텐츠가 없습니다. 먼저 뉴스 번호를 선택해주세요.")

        # 4. 캡션 수정 (발행 대기 중 텍스트 입력)
        elif status == "awaiting_publish" and len(text) > 5:
            updated = {**state, "pending_caption": text}
            sm.save(updated)
            state = updated
            send_message(f"✅ 캡션 저장됨:\n\n{text}\n\n**발행해줘** 로 업로드하세요.")


if __name__ == "__main__":
    main()
