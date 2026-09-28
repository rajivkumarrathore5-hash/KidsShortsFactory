import os
import requests
from pathlib import Path
from config import get_secret
from uploaders.metadata import generate_youtube_metadata


def _resolve_page_credentials():
    """
    Retrieves FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN from config/secrets.
    If the provided token is a User Access Token or the Page ID requires resolution,
    it queries /me/accounts to obtain the Page Access Token for Bhakti Beats.
    """
    page_id = str(get_secret("FB_PAGE_ID", "450166581524270")).strip()
    page_token = str(get_secret("FB_PAGE_ACCESS_TOKEN", "")).strip()

    if not page_token:
        return page_id, page_token, "Bhakti Beats"

    # Known Bhakti Beats Page ID
    bhakti_beats_page_id = "450166581524270"
    page_name = "Bhakti Beats"

    # If page_id is missing or set to the profile/short ID, use known Bhakti Beats ID
    if not page_id or page_id == "6159861104121":
        page_id = bhakti_beats_page_id

    # Try quick check on the page endpoint
    try:
        check_url = f"https://graph.facebook.com/v20.0/{page_id}"
        resp = requests.get(
            check_url,
            params={"fields": "id,name", "access_token": page_token},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("id", page_id), page_token, data.get("name", page_name)
    except Exception:
        pass

    # If direct query failed, check if page_token is a user token with access to /me/accounts
    try:
        accounts_url = "https://graph.facebook.com/v20.0/me/accounts"
        resp = requests.get(
            accounts_url,
            params={"access_token": page_token},
            timeout=10,
        )
        if resp.status_code == 200:
            accounts = resp.json().get("data", [])
            # Search for Bhakti Beats or matching page_id
            for acc in accounts:
                if acc.get("id") == page_id or "bhakti beats" in acc.get("name", "").lower():
                    return acc["id"], acc["access_token"], acc.get("name", page_name)
    except Exception:
        pass

    return page_id, page_token, page_name


def upload_to_facebook(
    video_path,
    title=None,
    description=None,
    tags=None,
    script=None,
    theme=None,
    character=None,
):
    """
    Uploads a video to Facebook Page using Facebook Graph API v20.0.
    Endpoint: POST https://graph.facebook.com/v20.0/{FB_PAGE_ID}/videos
    """
    video_path = Path(video_path)
    if not video_path.is_file():
        print(f"[FB] Error: Video file not found: {video_path}")
        return None

    page_id, access_token, page_name = _resolve_page_credentials()

    if not access_token:
        print("[FB] Error: Facebook credentials missing. Please set FB_PAGE_ACCESS_TOKEN in secrets.py.")
        return None

    if not page_id:
        print("[FB] Error: Facebook Page ID missing. Please set FB_PAGE_ID in secrets.py.")
        return None

    # Generate or format metadata if missing
    if not title or not description:
        script_text = script or description or title or "Kids Short Devotional Story"
        try:
            metadata = generate_youtube_metadata(script_text, theme=theme, character=character)
            if not title:
                title = metadata.get("title", "Bhakti Story #shorts")
            if not description:
                description = metadata.get("description", "")
            if not tags and metadata.get("tags"):
                tags = metadata.get("tags")
        except Exception as meta_err:
            print(f"[FB] Warning: Metadata generation failed ({meta_err}), using default title/description.")
            if not title:
                title = f"Divine Story of {character or theme or 'Bhakti'} #shorts #viral #bhakti"
            if not description:
                description = f"Watch this divine short story! 🙏\n\n#shorts #viral #bhakti #{character or 'krishna'}"

    # Format title & description
    final_title = str(title).strip()[:100]
    final_desc = str(description).strip()
    if tags and isinstance(tags, (list, tuple)):
        tag_str = " ".join(f"#{t.replace(' ', '')}" for t in tags if str(t).strip() and not str(t).startswith("#"))
        if tag_str and tag_str not in final_desc:
            final_desc = f"{final_desc}\n\n{tag_str}".strip()

    final_desc = final_desc[:5000]

    print(f"[FB] Uploading to {page_name}...")

    upload_url = f"https://graph.facebook.com/v20.0/{page_id}/videos"
    data = {
        "title": final_title,
        "description": final_desc,
        "access_token": access_token,
    }

    try:
        with open(video_path, "rb") as video_file:
            files = {
                "source": (video_path.name, video_file, "video/mp4"),
            }
            response = requests.post(
                upload_url,
                data=data,
                files=files,
                timeout=300,
            )

        resp_json = {}
        try:
            resp_json = response.json()
        except Exception:
            resp_json = {}

        if response.status_code == 200 and "id" in resp_json:
            video_id = resp_json["id"]
            video_url = f"https://www.facebook.com/watch/?v={video_id}"
            print(f"[FB] Success: {video_url}")
            return {"id": video_id, "url": video_url}

        # Error Handling
        err_info = resp_json.get("error", {})
        err_msg = err_info.get("message", response.text)
        err_code = err_info.get("code")
        err_subcode = err_info.get("error_subcode")

        if err_code == 190 or "access token" in err_msg.lower() or "session" in err_msg.lower():
            print(f"[FB] Error: Facebook Access Token expired or invalid (Code {err_code}). Please update FB_PAGE_ACCESS_TOKEN in secrets.py.")
        elif err_code in {4, 17, 32, 613} or "rate limit" in err_msg.lower() or "calls to this api" in err_msg.lower():
            print(f"[FB] Error: Facebook Rate Limit exceeded (Code {err_code}). Please try again later.")
        else:
            print(f"[FB] Error: Facebook upload failed (Status {response.status_code}, Code {err_code}, Subcode {err_subcode}): {err_msg}")

        return None

    except requests.exceptions.Timeout:
        print(f"[FB] Error: Connection timed out while uploading {video_path.name} to Facebook.")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"[FB] Error: Network error during Facebook upload: {req_err}")
        return None
    except Exception as e:
        print(f"[FB] Error: Unexpected exception during Facebook upload: {e}")
        return None


# Alias for factory integration
def upload(video_path, title=None, description=None, script=None, theme=None, character=None, tags=None):
    return upload_to_facebook(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        script=script,
        theme=theme,
        character=character,
    )
