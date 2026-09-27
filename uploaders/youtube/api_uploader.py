import os
import unicodedata
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import get_secret, SCHEDULE_INTERVAL_HOURS, MADE_FOR_KIDS
from pipeline.pre_run_settings import load_config_state, CONFIG_STATE_PATH
from uploaders.metadata import generate_youtube_metadata



PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIENT_SECRET_FILE = PROJECT_ROOT / get_secret(
    "YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json"
)
TOKEN_FILE = PROJECT_ROOT / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
STOP_WORDS = {
    "aur", "hai", "hain", "ho", "hum", "humare", "ki", "ka", "ke", "ko",
    "kya", "mein", "me", "ne", "par", "se", "tha", "the", "to", "tum",
    "ya", "ye", "yes", "you", "the", "and", "for", "with", "from", "this",
    "that", "are", "was", "were", "have", "has", "had", "will", "your",
    "और", "है", "हैं", "हो", "का", "की", "के", "को", "में", "से", "पर",
    "तो", "यह", "वह", "हम", "भी", "एक",
}


def _get_youtube_service():
    credentials = None
    if TOKEN_FILE.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            print(f"[WARNING] Token file invalid or corrupt: {e}")
            credentials = None

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as e:
            print(f"[WARNING] Token refresh failed: {e}, initiating new OAuth flow...")
            credentials = None

    if not credentials or not credentials.valid:
        if not CLIENT_SECRET_FILE.is_file():
            raise FileNotFoundError(
                f"YouTube OAuth client file not found: {CLIENT_SECRET_FILE}. Please ensure client_secret.json exists in project root."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE), SCOPES
        )
        credentials = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def _tags_from_script(script):
    words = []
    current_word = []
    for character in unicodedata.normalize("NFKC", script).casefold():
        category = unicodedata.category(character)
        if category[0] in {"L", "M", "N"}:
            current_word.append(character)
        elif current_word:
            words.append("".join(current_word))
            current_word = []
    if current_word:
        words.append("".join(current_word))

    words = Counter(
        word for word in words if len(word) >= 2 and word not in STOP_WORDS
    )
    tags = []
    total_length = 0
    for word, _ in words.most_common():
        tag = word[:30]
        if total_length + len(tag) > 450:
            break
        tags.append(tag)
        total_length += len(tag)
        if len(tags) == 15:
            break
    return tags


def get_next_publish_time(config_state, interval_hours):
    now_utc = datetime.now(timezone.utc)
    raw_next = config_state.get("next_publish_time")

    dt_publish_at = None
    if raw_next:
        try:
            dt = datetime.fromisoformat(raw_next.replace("Z", "+00:00"))
            if dt > now_utc:
                dt_publish_at = dt
        except Exception:
            dt_publish_at = None

    if not dt_publish_at:
        dt_publish_at = now_utc + timedelta(hours=interval_hours)

    return dt_publish_at


def check_rate_limit(config_state):
    history = config_state.get("upload_history", [])
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=24)

    recent_count = 0
    for item in history:
        uploaded_at_str = item.get("uploaded_at")
        if uploaded_at_str:
            try:
                dt = datetime.fromisoformat(uploaded_at_str.replace("Z", "+00:00"))
                if dt >= cutoff:
                    recent_count += 1
            except Exception:
                pass

    if recent_count >= 5:
        print("[WARNING] Rate limit protection: 5 uploads already performed in the last 24 hours. Aborting upload.")
        return False
    return True


def upload(video_path, title=None, description=None, script=None, theme=None, character=None):
    video_path = Path(video_path)
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    config_state = load_config_state()

    # Rate Limit Check (Requirement 7)
    if not check_rate_limit(config_state):
        return None

    interval_hours = SCHEDULE_INTERVAL_HOURS
    publish_at_dt = get_next_publish_time(config_state, interval_hours)
    publish_at_iso = publish_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    next_slot_dt = publish_at_dt + timedelta(hours=interval_hours)
    next_slot_iso = next_slot_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # AI Metadata Generation (Requirement 4)
    script_text = script or description or title or "Kids Short Story"
    metadata = generate_youtube_metadata(script_text, theme=theme, character=character)

    final_title = (title or metadata["title"]).strip()[:100]
    final_description = (description or metadata["description"]).strip()[:5000]
    tags = metadata.get("tags") or _tags_from_script(script_text)

    # Required scheduling logs (Requirement 2)
    print(f"[UPLOAD] Uploading video: {video_path.name}")
    print(f"[UPLOAD] Title: {final_title}")
    print(f"[UPLOAD] Scheduled to go public at: {publish_at_iso}")
    print(f"[UPLOAD] Next scheduled slot: {next_slot_iso}")
    print(f"[UPLOAD] Made for Kids: {MADE_FOR_KIDS} (target audience: {'kids' if MADE_FOR_KIDS else 'adults'})")

    youtube = _get_youtube_service()

    # Select Category: "24" (Entertainment) or "22" (People & Blogs)
    script_lower = script_text.lower()
    if any(k in script_lower for k in ["krishna", "hanuman", "story", "kahani", "animation", "kids", "fun"]):
        category_id = "24"
    else:
        category_id = "22"

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": final_title,
                "description": final_description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_at_iso,
                "selfDeclaredMadeForKids": MADE_FOR_KIDS,
            },
        },
        media_body=MediaFileUpload(
            str(video_path), chunksize=8 * 1024 * 1024, resumable=True
        ),
    )


    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    video_url = f"https://youtu.be/{video_id}"

    # Save next_publish_time and upload_history to config_state.json
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    upload_history = config_state.get("upload_history", [])
    upload_history.append({
        "video_id": video_id,
        "uploaded_at": now_iso,
        "publish_at": publish_at_iso,
    })

    config_state["next_publish_time"] = next_slot_iso
    config_state["upload_history"] = upload_history

    try:
        import json
        CONFIG_STATE_PATH.write_text(json.dumps(config_state, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARNING] Could not update config_state.json after upload: {e}")

    print(f"[UPLOAD] Success: {video_url}")
    return {"id": video_id, "url": video_url, "publish_at": publish_at_iso}