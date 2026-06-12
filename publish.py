#!/usr/bin/env python3
"""
GitHub Actions: pending/ 폴더에서 approved 콘텐츠 찾아 Instagram 발행
"""
import os
import sys
import time
import requests
import yaml
from pathlib import Path

IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG_BUSINESS_ACCOUNT_ID = os.environ["IG_BUSINESS_ACCOUNT_ID"]
BASE = f"https://graph.facebook.com/v19.0"


def graph(method, path, **data):
    resp = requests.request(
        method,
        f"{BASE}/{path}",
        params={"access_token": IG_ACCESS_TOKEN},
        json=data or None,
    )
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"Graph API 오류: {result['error']}")
    return result


def wait_ready(cid, tries=30, delay=5):
    for _ in range(tries):
        s = graph("GET", f"{cid}?fields=status_code").get("status_code")
        print(f"  상태: {s}")
        if s == "FINISHED":
            return
        if s == "ERROR":
            raise RuntimeError("컨테이너 처리 오류")
        time.sleep(delay)
    raise TimeoutError("컨테이너 준비 타임아웃")


def find_approved():
    pending = Path("pending")
    if not pending.exists():
        return None, None
    for folder in sorted(pending.iterdir(), reverse=True):
        sp = folder / "status.yaml"
        if not sp.exists():
            continue
        status = yaml.safe_load(sp.read_text())
        if status.get("state") == "approved":
            return folder, status
    return None, None


def load_caption(folder):
    parts = []
    if (folder / "caption.txt").exists():
        parts.append((folder / "caption.txt").read_text().strip())
    if (folder / "hashtags.txt").exists():
        tags = (folder / "hashtags.txt").read_text().strip().split()
        parts.append(" ".join(f"#{t.lstrip('#')}" for t in tags))
    return "\n\n".join(parts)


def publish_carousel(urls, caption):
    children = [
        graph("POST", f"{IG_BUSINESS_ACCOUNT_ID}/media",
              image_url=u, is_carousel_item=True)["id"]
        for u in urls
    ]
    cid = graph("POST", f"{IG_BUSINESS_ACCOUNT_ID}/media",
                media_type="CAROUSEL",
                children=",".join(children),
                caption=caption)["id"]
    wait_ready(cid)
    return graph("POST", f"{IG_BUSINESS_ACCOUNT_ID}/media_publish",
                 creation_id=cid)["id"]


def publish_image(url, caption):
    cid = graph("POST", f"{IG_BUSINESS_ACCOUNT_ID}/media",
                image_url=url, caption=caption)["id"]
    wait_ready(cid)
    return graph("POST", f"{IG_BUSINESS_ACCOUNT_ID}/media_publish",
                 creation_id=cid)["id"]


def main():
    folder, status = find_approved()
    if not folder:
        print("pending/ 에 approved 콘텐츠 없음 — 종료")
        sys.exit(0)

    print(f"발행 대상: {folder.name}")
    caption = load_caption(folder)
    media_type = status.get("media_type", "IMAGE").upper()

    if media_type == "CAROUSEL":
        media_id = publish_carousel(status["public_urls"], caption)
    elif media_type == "IMAGE":
        media_id = publish_image(status["public_url"], caption)
    else:
        print(f"지원하지 않는 media_type: {media_type}")
        sys.exit(1)

    print(f"✅ 발행 완료 media_id={media_id}")

    status["state"] = "published"
    status["media_id"] = media_id
    (folder / "status.yaml").write_text(
        yaml.dump(status, allow_unicode=True, sort_keys=False)
    )


if __name__ == "__main__":
    main()
