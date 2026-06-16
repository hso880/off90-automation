#!/usr/bin/env python3
"""
카카오톡 '나에게 보내기' — refresh_token → access_token → 메시지 발송
"""
import os
import json
import requests

KAKAO_REST_API_KEY = os.environ["KAKAO_REST_API_KEY"]
KAKAO_REFRESH_TOKEN = os.environ["KAKAO_REFRESH_TOKEN"]
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_ME_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _refresh_access_token():
    token_data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN,
    }
    if KAKAO_CLIENT_SECRET:
        token_data["client_secret"] = KAKAO_CLIENT_SECRET
    resp = requests.post(
        TOKEN_URL,
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"토큰 갱신 실패: {data}")
    return data["access_token"]


def send_me(text: str):
    """나에게 텍스트 메시지 발송."""
    access_token = _refresh_access_token()
    template = {
        "object_type": "text",
        "text": text[:2000],  # 카카오 텍스트 메시지 최대 2000자
        "link": {
            "web_url": "https://instagram.com/the.off90",
            "mobile_web_url": "https://instagram.com/the.off90",
        },
    }
    resp = requests.post(
        SEND_ME_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
    )
    result = resp.json()
    if result.get("result_code") != 0:
        raise RuntimeError(f"메시지 전송 실패: {result}")
    print("✅ 카카오톡 전송 완료")


if __name__ == "__main__":
    # 간단 테스트
    send_me("⚽ OFF90봇 테스트 메시지입니다.")
