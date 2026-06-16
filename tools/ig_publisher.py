import os
import time
import requests


def upload_to_cloudinary(image_path_or_url):
    """Cloudinary 업로드 → secure_url"""
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
        secure=True,
    )
    result = cloudinary.uploader.upload(
        str(image_path_or_url),
        folder="off90/auto",
        resource_type="image",
    )
    return result["secure_url"]


def publish_carousel(image_paths_or_urls: list, caption: str) -> str:
    """이미지 리스트 → Cloudinary → Instagram 캐러셀 발행"""
    print(f"  Cloudinary 업로드 {len(image_paths_or_urls)}장...")
    urls = [upload_to_cloudinary(p) for p in image_paths_or_urls]
    print(f"  업로드 완료: {urls}")

    ig_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]
    token = os.environ["IG_ACCESS_TOKEN"]
    base = f"https://graph.facebook.com/v21.0/{ig_id}"

    children = []
    for url in urls:
        r = requests.post(f"{base}/media", data={
            "image_url": url, "is_carousel_item": "true", "access_token": token,
        })
        r.raise_for_status()
        children.append(r.json()["id"])

    r = requests.post(f"{base}/media", data={
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
        "access_token": token,
    })
    r.raise_for_status()
    container_id = r.json()["id"]

    for _ in range(12):
        r = requests.get(f"https://graph.facebook.com/v21.0/{container_id}",
                         params={"fields": "status_code", "access_token": token})
        if r.json().get("status_code") == "FINISHED":
            break
        time.sleep(5)

    r = requests.post(f"{base}/media_publish", data={
        "creation_id": container_id, "access_token": token,
    })
    r.raise_for_status()
    media_id = r.json()["id"]
    print(f"  ✅ Instagram 발행 완료: {media_id}")
    return media_id
