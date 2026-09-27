import base64
import io
from pathlib import Path
import requests
from PIL import Image

from config import get_secret, CLOUDFLARE_MODEL


def generate_agnes_image(prompt, output_path, width=1080, height=1920, seed=None):
    api_key = get_secret("AGNES_AI_API_KEY")
    if not api_key:
        raise ValueError("AGNES_AI_API_KEY is missing from secrets.py")
    if not prompt.strip():
        raise ValueError("Image prompt is empty")

    url = "https://apihub.agnes-ai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "agnes-image-2.1-flash",
        "prompt": prompt,
        "size": f"{width}x{height}",
        "n": 1,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        # If custom size is rejected by Agnes API, try nearest standard size
        nearest_size = "1024x1792" if height > width else ("1024x1024" if height == width else "1792x1024")
        print(f"[WARN] Agnes AI rejected custom size {width}x{height} (HTTP {response.status_code}); retrying with nearest standard size {nearest_size}...")
        payload["size"] = nearest_size
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            detail = response.text[:200]
            raise ValueError(f"HTTP {response.status_code}: {detail}")

    data = response.json()
    image_url = None
    b64_data = None
    if isinstance(data, dict) and "data" in data and len(data["data"]) > 0:
        item = data["data"][0]
        image_url = item.get("url")
        b64_data = item.get("b64_json")

    image_bytes = None
    if image_url:
        img_res = requests.get(image_url, timeout=60)
        if img_res.status_code == 200:
            image_bytes = img_res.content
        else:
            raise ValueError(f"Failed to download image URL: HTTP {img_res.status_code}")
    elif b64_data:
        image_bytes = base64.b64decode(b64_data)
    else:
        raise ValueError(f"Unexpected response format from Agnes AI: {data}")

    if not image_bytes:
        raise ValueError("Agnes AI returned no image bytes")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(image_bytes)) as img:
        img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS).save(output, format="JPEG", quality=92)
    return str(output)


def generate_cloudflare_image(prompt, output_path, width=1080, height=1920, seed=None):
    api_token = get_secret("CLOUDFLARE_API_TOKEN")
    account_id = get_secret("CLOUDFLARE_ACCOUNT_ID")
    if not api_token or not account_id:
        raise ValueError("CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID is missing from secrets.py")
    if not prompt.strip():
        raise ValueError("Image prompt is empty")

    model = CLOUDFLARE_MODEL or "@cf/black-forest-labs/flux-1-schnell"
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        detail = response.text[:200]
        raise ValueError(f"HTTP {response.status_code}: {detail}")

    content_type = response.headers.get("content-type", "")
    image_bytes = None

    if "image" in content_type or response.content.startswith(b"\xff\xd8") or response.content.startswith(b"\x89PNG"):
        image_bytes = response.content
    else:
        try:
            data = response.json()
            if isinstance(data, dict):
                res = data.get("result", {})
                b64 = res.get("image") if isinstance(res, dict) else None
                if b64:
                    image_bytes = base64.b64decode(b64)
        except Exception:
            pass

    if not image_bytes:
        image_bytes = response.content

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(image_bytes)) as img:
        img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS).save(output, format="JPEG", quality=92)
    return str(output)
