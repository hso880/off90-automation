#!/usr/bin/env python3
"""
Discord 폴링 응답기 (5분마다 실행)

상태 흐름:
  awaiting_story_selection → (번호) → awaiting_photo_confirm
  awaiting_photo_confirm   → (OK)   → generating → awaiting_publish
  awaiting_photo_confirm   → (N번 바꿔) → awaiting_photo_confirm (해당 슬라이드 교체)
  awaiting_publish         → (발행해줘) → published
"""
import os, sys, tempfile, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.discord_bot import get_recent_messages, send_message, send_photo_confirm, send_carousel_preview
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


def _auto_select_photos(content_type: str, data: dict) -> dict:
    """슬라이드별 최적 사진 1장씩 자동 검색 → {s1, s2, s3}"""
    from tools.naver_image import search_images, slide1_queries, slide2_query, slide3_query

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

    return {"s1": photo_s1, "s2": photo_s2, "s3": photo_s3}


def _replace_slide_photo(slot: str, content_type: str, data: dict,
                          current_photos: dict, tried: list) -> dict:
    """특정 슬라이드 사진 교체 검색 (이전에 사용한 URL 제외)"""
    from tools.naver_image import search_images, slide1_queries, slide2_query, slide3_query

    if slot == "s1":
        candidates = []
        for q in slide1_queries(content_type, data):
            candidates += search_images(q, count=3)
    elif slot == "s2":
        candidates = search_images(slide2_query(content_type, data), count=5)
    else:
        candidates = search_images(slide3_query(content_type, data), count=5)

    # 이전에 쓴 URL 제외
    fresh = [u for u in candidates if u not in tried]
    new_url = fresh[0] if fresh else (candidates[0] if candidates else current_photos.get(slot, ""))

    updated = dict(current_photos)
    updated[slot] = new_url
    return updated


def handle_story_selection(choice: int, state: dict):
    """번호 선택 → 데이터 추출 + 사진 자동 검색 → 확인 요청"""
    news_list = state.get("news_list", {})
    item = news_list.get(str(choice))
    if not item:
        send_message(f"1~{len(news_list)} 사이의 번호를 입력해주세요.")
        return

    content_type, story = item[0], item[1]
    title = story.get("title_ko") or story.get("title", "")

    msg = send_message(f"🔍 **{title[:70]}**\n\n콘텐츠에 맞는 사진 검색 중...")
    sm.save({**state, "status": "searching", "last_message_id": msg["id"]})

    from tools.carousel_builder import extract_worldcup_data, extract_transfer_data

    if content_type == "worldcup":
        data = extract_worldcup_data(title, story.get("published", ""))
    else:
        data = extract_transfer_data(title, story.get("published", ""), story.get("priority", 1))

    photos = _auto_select_photos(content_type, data)
    print(f"S1: {photos['s1'][:60] if photos['s1'] else '없음'}")
    print(f"S2: {photos['s2'][:60] if photos['s2'] else '없음'}")
    print(f"S3: {photos['s3'][:60] if photos['s3'] else '없음'}")

    confirm_msg = send_photo_confirm(photos, title)

    sm.save({
        "status": "awaiting_photo_confirm",
        "content_type": content_type,
        "story": story,
        "extracted_data": data,
        "photos": photos,
        "tried_urls": list(photos.values()),
        "last_message_id": confirm_msg["id"],
    })


def handle_photo_confirm(text: str, state: dict):
    """OK / 다시 / N번 바꿔 처리"""
    content_type = state.get("content_type", "worldcup")
    story = state.get("story", {})
    title = story.get("title_ko") or story.get("title", "")
    data = state.get("extracted_data", {})
    photos = dict(state.get("photos", {}))
    tried = list(state.get("tried_urls", []))

    text_lower = text.lower().strip()

    # 전체 재검색
    if text_lower in ("다시", "재검색", "retry"):
        msg = send_message("🔄 사진 새로 검색 중...")
        sm.save({**state, "last_message_id": msg["id"]})
        photos = _auto_select_photos(content_type, data)
        tried += list(photos.values())
        confirm_msg = send_photo_confirm(photos, title)
        sm.save({**state,
                 "photos": photos,
                 "tried_urls": tried,
                 "last_message_id": confirm_msg["id"]})
        return

    # 특정 슬라이드 교체: "1번 바꿔", "2번 바꿔", "3번 바꿔"
    replace_m = re.search(r"([123])번\s*바꿔", text)
    if replace_m:
        slot = f"s{replace_m.group(1)}"
        msg = send_message(f"🔄 슬라이드{replace_m.group(1)} 사진 교체 중...")
        sm.save({**state, "last_message_id": msg["id"]})
        photos = _replace_slide_photo(slot, content_type, data, photos, tried)
        tried.append(photos[slot])
        confirm_msg = send_photo_confirm(photos, title)
        sm.save({**state,
                 "photos": photos,
                 "tried_urls": tried,
                 "last_message_id": confirm_msg["id"]})
        return

    # OK → 캐러셀 제작
    if text_lower in ("ok", "ок", "오케이", "좋아", "이대로", "go"):
        _build_and_preview(state, data, photos)


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

        # 캡션 초안
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

    if status in ("generating", "searching"):
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

        # 1. 뉴스 번호 선택 — "3", "1, 6", "3번" 등 다양한 형식 허용
        _num_m = re.search(r'\d+', text)
        if status == "awaiting_story_selection" and _num_m:
            handle_story_selection(int(_num_m.group()), state)
            state = sm.load()

        # 2. 사진 확인 (OK / 다시 / N번 바꿔)
        elif status == "awaiting_photo_confirm":
            text_lower = text.lower().strip()
            if (text_lower in ("ok", "ок", "오케이", "좋아", "이대로", "go")
                    or text_lower in ("다시", "재검색", "retry")
                    or re.search(r"[123]번\s*바꿔", text)):
                handle_photo_confirm(text, state)
                state = sm.load()

        # 3. 발행 명령
        elif any(kw in text for kw in PUBLISH_KW):
            if status == "awaiting_publish":
                handle_publish(state)
                state = sm.load()
            else:
                send_message("발행할 콘텐츠가 없습니다. 먼저 뉴스 목록에서 번호를 선택해주세요.")

        # 4. 캡션 수정
        elif status == "awaiting_publish" and len(text) > 5 and not text.startswith("/"):
            updated = {**state, "pending_caption": text}
            sm.save(updated)
            state = updated
            send_message(f"✅ 캡션 저장됨:\n\n{text}\n\n**발행해줘** 로 업로드하세요.")

        # 5. 취소
        elif text in ("취소", "/취소", "cancel"):
            sm.clear()
            send_message("✅ 취소됐습니다. 다음 오전 8시에 새 뉴스가 옵니다.")

        # 6. 도움말
        elif text.lower() in ("/help", "도움말"):
            send_message(
                "⚽ **OFF90 자동화 봇**\n\n"
                "① 뉴스 번호 입력 → 사진 자동 검색\n"
                "② **OK** / **다시** / **N번 바꿔** → 사진 확인\n"
                "③ 캐러셀 자동 제작 (~60초)\n"
                "④ (선택) 캡션 수정\n"
                "⑤ **발행해줘** → Instagram 업로드\n\n"
                "**취소** 로 초기화"
            )


if __name__ == "__main__":
    main()
