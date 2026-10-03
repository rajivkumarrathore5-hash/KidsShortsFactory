import os
import random
import urllib.parse
from pathlib import Path
import requests

from config import get_secret

POLLINATIONS_API_KEY = get_secret("POLLINATIONS_API_KEY", "")


def generate_ai_music(prompt, output_path, duration=25):
    """
    Generates music using Pollinations AI audio API or falls back to static music files.
    Returns path to music file if available, or None if failed and no fallback available.
    """
    if not prompt:
        prompt = "soft flute romantic devotional Indian classical gentle tabla"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    encoded_prompt = urllib.parse.quote(prompt.strip())
    url = (
        f"https://gen.pollinations.ai/audio/{encoded_prompt}"
        f"?model=elevenmusic&duration={duration}&key={POLLINATIONS_API_KEY}"
    )

    print(f"[AI MUSIC] Generating music via Pollinations API...")
    print(f"[AI MUSIC] Prompt: '{prompt}', duration: {duration}s")

    try:
        response = requests.get(url, timeout=90)
        if response.status_code == 200 and len(response.content) > 1000:
            output_path.write_bytes(response.content)
            print(f"[AI MUSIC] Music successfully generated and saved to {output_path}")
            return str(output_path)
        else:
            print(
                f"[AI MUSIC] Pollinations API returned status {response.status_code}, "
                f"content length: {len(response.content)}"
            )
    except Exception as error:
        print(f"[AI MUSIC] API request failed: {error}")

    print("[AI MUSIC] Falling back to static music from data/music/ or assets/music/...")
    project_root = Path(__file__).resolve().parents[1]
    for music_dir in [project_root / "data" / "music", project_root / "assets" / "music"]:
        if music_dir.is_dir():
            music_files = [
                file_path
                for file_path in music_dir.glob("*")
                if file_path.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a")
                and file_path.is_file()
            ]
            if music_files:
                fallback = random.choice(music_files)
                print(f"[AI MUSIC] Fallback music selected: {fallback}")
                return str(fallback)

    print("[AI MUSIC] No fallback music available. Skipping background music.")
    return None
