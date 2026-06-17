#!/usr/bin/env python3
"""
Discord 폴링 응답기 (5분마다 실행)
흐름: 번호 입력 → 캐러셀 자동 제작 → 미리보기 → 발행해줘 → Instagram
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


def handle_story_selection(choice: int, state: dict):
    """번호 선택 → 자동 사진 검색 → 캐러셀 제작 → Discord 미리보기"""
    news_list = state.get("news_list", {})
    item = news_list.get(str(choice))
    if not item:
        total = len(news_list)
        send_message(f"1~{total} 사이의 번호를 입력해주세요.")
        return

    content_type, story = item[0], item[1]
    title = story.get("title_ko") or story.get("title", "")

    msg = send_message(f"🎨 **{title[:70]}**\n\n캐러셀 제작 중... (약 60초 소요)")
    sm.save({**state, "status": "generating", "last_message_id": msg["id"]})

    from tools.carousel_builder import extract_worldcup_data, extract_transfer_data, build_html, render
    from tools.naver_image import search_images, slide1_queries, slide2_query, slide3_query

    # ── 데이터 추출 ──────────────────────────────
    if content_type == "worldcup":
        data = extract_worldcup_data(title, story.get("published", ""))
    else:
        data = extract_transfer_data(title, story.get("published", ""), story.get("priority", 1))

    # ── 사진 자동 선택 ───────────────────────────
    # 슬라이드 1: 첫 번째 쿼리에서 가장 좋은 사진
    photo_s1 = ""
    for q in slide1_queries(content_type, data):
        imgs = search_images(q, count=1)
        if imgs:
            photo_s1 = imgs[0]
            break

    q2_imgs = search_images(slide2_query(content_type, data), count=1)
    photo_s2 = q2_imgs[0] if q2_imgs else photo_s1

    q3_imgs = search_images(slide3_query(content_type, data), count=1)
    photo_s3 = q3_imgs[0] if q3_imgs else photo_s2 or photo_s1

    print(f"S1: {photo_s1[:60] if photo_s1 else '없음'}")
    print(f"S2: {photo_s2[:60] if photo_s2 else '없음'}")
    print(f"S3: {photo_s3[:60] if photo_s3 else '없음'}")

    # ── 캐러셀 빌드 + 렌더 ──────────────────────
    html = build_html(data, photo_s1, photo_s2, photo_s3)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        slide_paths = render(html, tmp_path)

        if not slide_paths:
            send_message("❌ 캐러셀 생성 실패. 다시 번호를 입력해주세요.")
            sm.save({**state, "status": "awaiting_story_selection"})
            return

        # ── Cloudinary 업로드 ────────────────────
        from tools.ig_publisher import upload_to_cloudinary
        cloudinary_urls = []
        for p in slide_paths:
            try:
                cloudinary_urls.append(upload_to_cloudinary(p))
            except Exception as e:
                print(f"Cloudinary 업로드 실패: {e}")

        # ── 캡션 초안 ────────────────────────────
        if content_type == "worldcup":
            ta = data.get("team_a", "")
            tb = data.get("team_b", "")
            sa = data.get("score_a", "")
            sb = data.get("score_b", "")
            draft = (
                f"{ta} {sa}-{sb} {tb}\n\n"
                f"{title}\n\n"
                f"#월드컵2026 #{ta.lower()} #{tb.lower()} #2026월드컵 #FIFA월드컵 #off90"
            )
        else:
            player = data.get("player", "").replace(" ", "")
            club   = (data.get("to_club") or data.get("from_club", "")).replace(" ", "")
            draft = (
                f"{title}\n\n"
                f"#이적시장 #해외축구 #2026이적 #{player} "
                f"#{club if club else '축구'} #off90"
            )

        # ── Discord 미리보기 발송 ─────────────────
        preview_msg = send_carousel_preview(slide_paths, draft)

    sm.save({
        "status": "awaiting_publish",
        "content_type": content_type,
        "story": story,
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
        if not text:
            continue

        sm.save({**state, "last_message_id": msg["id"]})
        state = sm.load()
        status = state.get("status", "idle")

        # ── 뉴스 번호 선택 ──────────────────────
        if status == "awaiting_story_selection" and text.isdigit():
            handle_story_selection(int(text), state)
            state = sm.load()

        # ── 발행 명령 ───────────────────────────
        elif any(kw in text for kw in PUBLISH_KW):
            if status == "awaiting_publish":
                handle_publish(state)
                state = sm.load()
            else:
                send_message(
                    "발행할 콘텐츠가 없습니다.\n"
                    "먼저 뉴스 목록에서 번호를 선택해주세요."
                )

        # ── 캡션 수정 ───────────────────────────
        elif status == "awaiting_publish" and len(text) > 5 and not text.startswith("/"):
            updated = {**state, "pending_caption": text}
            sm.save(updated)
            state = updated
            send_message(
                f"✅ 캡션 저장됨:\n\n{text}\n\n"
                "**발행해줘** 라고 입력하면 Instagram에 올려드릴게요."
            )

        # ── 도움말 ─────────────────────────────
        elif text.lower() in ("/help", "도움말"):
            send_message(
                "⚽ **OFF90 자동화 봇**\n\n"
                "① 뉴스 번호 입력 → 캐러셀 자동 제작\n"
                "② (선택) 캡션 수정 입력\n"
                "③ **발행해줘** → Instagram 자동 업로드\n\n"
                "취소하려면 **취소** 입력"
            )

        # ── 취소 ───────────────────────────────
        elif text in ("취소", "/취소", "cancel"):
            sm.clear()
            send_message("✅ 취소됐습니다. 다음 오전 8시에 새 뉴스가 옵니다.")


if __name__ == "__main__":
    main()
