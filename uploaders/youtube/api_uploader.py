import os
import unicodedata
from collections import Counter
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import get_secret


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
        credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    elif not credentials or not credentials.valid:
        if not CLIENT_SECRET_FILE.is_file():
            raise FileNotFoundError(
                f"YouTube OAuth client file not found: {CLIENT_SECRET_FILE}"
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


def upload(video_path, title, description, script=None):
    video_path = Path(video_path)
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    script = script or description or title
    title = (title or next(iter(script.splitlines()), "Kids Short")).strip()[:100]
    description = (description or script).strip()[:5000]
    privacy_status = os.getenv("YOUTUBE_PRIVACY_STATUS", "private").lower()
    if privacy_status not in {"private", "unlisted", "public"}:
        raise ValueError("YOUTUBE_PRIVACY_STATUS must be private, unlisted, or public.")

    youtube = _get_youtube_service()
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": _tags_from_script(script),
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": True,
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
    return {"id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}