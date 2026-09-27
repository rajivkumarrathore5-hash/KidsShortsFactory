from instagrapi import Client
from config import get_secret

def upload(video_path, title, description):
    username = get_secret("INSTA_USERNAME")
    password = get_secret("INSTA_PASSWORD")
    if not username or not password:
        print("⚠️ Instagram credentials not set. Skipping upload.")
        return "Instagram Upload Skipped (No Credentials)"
    cl = Client()
    cl.login(username, password)
    cl.clip_upload(video_path, caption=title + "\n\n" + description)
    return "Instagram Upload Success"
