import os

PROJECT_NAME = "KidsShortsFactory"

# ================================================================
#  FOLDER STRUCTURE
# ================================================================
folders = [
    "script_gen",
    "tts",
    "visuals",
    "video_engine",
    "uploaders/youtube",
    "uploaders/facebook",
    "uploaders/instagram",
    "outputs"
]

# ================================================================
#  FILES WITH CONTENT
# ================================================================
files = {}

# ---- ROOT FILES ----
files["config.py"] = '''import os
from dotenv import load_dotenv
load_dotenv()

PLATFORMS = ["youtube", "facebook", "instagram"]
SCRIPT_PROVIDER = "gemini"
TTS_PROVIDER = "edge"
VISUAL_PROVIDER = "pexels"
RENDER_ENGINE = "moviepy"
YOUTUBE_PROVIDER = "selenium"
FACEBOOK_PROVIDER = "selenium"
INSTAGRAM_PROVIDER = "instagrapi"
SHORT_DURATION = 18
ASPECT_RATIO = (1080, 1920)
UPLOAD_INTERVAL_HOURS = 7
FALLBACK_ENABLED = True
'''

files["main.py"] = '''import os
import random
from datetime import datetime
from script_gen.factory import get_script
from tts.factory import get_tts
from visuals.factory import get_visual
from video_engine.factory import get_render_engine
from uploaders.factory import upload_to_platforms

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_and_upload():
    print(f"\\n🎬 Starting new short generation... {datetime.now()}")
    script = get_script()
    print(f"Script: {script}")
    tts_func = get_tts()
    audio_path = os.path.join(OUTPUT_DIR, f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
    tts_func(script, audio_path)
    visual_func = get_visual()
    visual_url = visual_func()
    duration = random.randint(15, 20)
    video_path = os.path.join(OUTPUT_DIR, f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    engine = get_render_engine()
    engine(audio_path, script, video_path, visual_url, duration)
    title = f"Funny Kids Moment! 🐱 #Shorts"
    description = "Check out this funny kids video! #KidsFun #Cartoon"
    results = upload_to_platforms(video_path, title, description)
    print("✅ Done! Results:", results)
    return results

if __name__ == "__main__":
    create_and_upload()
'''

files["scheduler.py"] = '''import schedule
import time
from main import create_and_upload
from config import UPLOAD_INTERVAL_HOURS

print(f"🕒 Scheduler started. Uploading every {UPLOAD_INTERVAL_HOURS} hours.")
create_and_upload()
schedule.every(UPLOAD_INTERVAL_HOURS).hours.do(create_and_upload)
while True:
    schedule.run_pending()
    time.sleep(60)
'''

files["requirements.txt"] = '''google-generativeai
groq
edge-tts
moviepy
opencv-python-headless
requests
python-dotenv
schedule
instagrapi
playwright
'''

files[".env"] = '''GEMINI_API_KEY=
GROQ_API_KEY=
PEXELS_API_KEY=
INSTA_USERNAME=
INSTA_PASSWORD=
'''

# ---- script_gen ----
files["script_gen/__init__.py"] = ""
files["script_gen/factory.py"] = '''from config import SCRIPT_PROVIDER

def get_script():
    if SCRIPT_PROVIDER == "gemini":
        from . import gemini
        return gemini.generate_script()
    elif SCRIPT_PROVIDER == "groq":
        from . import groq
        return groq.generate_script()
    else:
        raise ValueError("Unknown SCRIPT_PROVIDER")
'''

files["script_gen/gemini.py"] = '''import google.generativeai as genai
import os
import random

def generate_script():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    topics = ["animals", "school life", "food", "superheroes", "space", "friendship"]
    topic = random.choice(topics)
    prompt = f"""
    Write a very short, funny, 15-second script for a kids' video.
    Topic: {topic}
    Tone: Playful, silly, cartoonish, like a 5-year-old talking.
    Language: Hinglish (mix of Hindi and English).
    Output: Only the spoken dialogue lines, maximum 3-4 lines.
    """
    response = model.generate_content(prompt)
    return response.text.strip()
'''

files["script_gen/groq.py"] = '''import os
from groq import Groq
import random

def generate_script():
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    topics = ["animals", "school", "funny food", "cartoon stories"]
    topic = random.choice(topics)
    prompt = f"Write a 15-second funny kids script in Hinglish. Topic: {topic}. Output: Just the dialogue."
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="mixtral-8x7b-32768",
    )
    return chat_completion.choices[0].message.content
'''

# ---- tts ----
files["tts/__init__.py"] = ""
files["tts/factory.py"] = '''from config import TTS_PROVIDER

def get_tts():
    if TTS_PROVIDER == "edge":
        from . import edge_tts
        return edge_tts.generate_audio
    elif TTS_PROVIDER == "coqui":
        from . import coqui_tts
        return coqui_tts.generate_audio
    else:
        raise ValueError("Unknown TTS_PROVIDER")
'''

files["tts/edge_tts.py"] = '''import edge_tts
import asyncio
import random

async def _generate(text, output_path):
    voices = ["en-US-JennyNeural", "en-GB-SoniaNeural"]
    voice = random.choice(voices)
    communicate = edge_tts.Communicate(text, voice, rate="+20%", pitch="+15Hz")
    await communicate.save(output_path)

def generate_audio(text, output_path):
    asyncio.run(_generate(text, output_path))
    return output_path
'''

# ---- visuals ----
files["visuals/__init__.py"] = ""
files["visuals/factory.py"] = '''from config import VISUAL_PROVIDER

def get_visual():
    if VISUAL_PROVIDER == "pexels":
        from . import pexels
        return pexels.get_video
    elif VISUAL_PROVIDER == "pixabay":
        from . import pixabay
        return pixabay.get_video
    else:
        raise ValueError("Unknown VISUAL_PROVIDER")
'''

files["visuals/pexels.py"] = '''import requests
import os
import random

def get_video(query=None):
    api_key = os.getenv("PEXELS_API_KEY")
    if not query:
        queries = ["kids animation", "cartoon background", "funny animals", "playful kids"]
        query = random.choice(queries)
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 1, "orientation": "portrait"}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    if data.get('videos'):
        video_files = data['videos'][0]['video_files']
        for f in video_files:
            if f.get('quality') == 'sd' or f.get('width', 0) <= 1080:
                return f['link']
    return None
'''

# ---- video_engine ----
files["video_engine/__init__.py"] = ""
files["video_engine/factory.py"] = '''from config import RENDER_ENGINE

def get_render_engine():
    if RENDER_ENGINE == "moviepy":
        from . import moviepy_engine
        return moviepy_engine.render_video
    elif RENDER_ENGINE == "ffmpeg":
        from . import ffmpeg_engine
        return ffmpeg_engine.render_video
    else:
        raise ValueError("Unknown RENDER_ENGINE")
'''

files["video_engine/moviepy_engine.py"] = '''from moviepy.editor import *
import requests
import os

def render_video(audio_path, text, output_path, visual_url=None, duration=18):
    if visual_url and visual_url.startswith('http'):
        resp = requests.get(visual_url)
        temp_vid = "temp_visual.mp4"
        with open(temp_vid, 'wb') as f:
            f.write(resp.content)
        bg_clip = VideoFileClip(temp_vid)
    else:
        bg_clip = ColorClip(size=(1080, 1920), color=(50, 150, 255), duration=duration)
    bg_clip = bg_clip.resize(height=1920)
    if bg_clip.w > 1080:
        bg_clip = bg_clip.crop(x_center=bg_clip.w/2, width=1080)
    audio_clip = AudioFileClip(audio_path)
    bg_clip = bg_clip.set_duration(audio_clip.duration)
    bg_clip = bg_clip.set_audio(audio_clip)
    txt_clip = TextClip(text, fontsize=70, color='yellow', font='Arial-Bold',
                        stroke_color='black', stroke_width=4)
    txt_clip = txt_clip.set_duration(audio_clip.duration)
    txt_clip = txt_clip.set_position(('center', 0.75), relative=True)
    final = CompositeVideoClip([bg_clip, txt_clip])
    final = final.resize(newsize=(1080, 1920))
    final.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    if visual_url and visual_url.startswith('http') and os.path.exists("temp_visual.mp4"):
        os.remove("temp_visual.mp4")
    return output_path
'''

# ---- uploaders ----
files["uploaders/__init__.py"] = ""
files["uploaders/factory.py"] = '''from config import PLATFORMS, YOUTUBE_PROVIDER, FACEBOOK_PROVIDER, INSTAGRAM_PROVIDER

def upload_to_platforms(video_path, title, description):
    results = {}
    if "youtube" in PLATFORMS:
        if YOUTUBE_PROVIDER == "api":
            from .youtube import api_uploader as yt
        else:
            from .youtube import internal_uploader as yt
        results['youtube'] = yt.upload(video_path, title, description)
    if "facebook" in PLATFORMS:
        if FACEBOOK_PROVIDER == "graph_api":
            from .facebook import graph_api as fb
        else:
            from .facebook import selenium_uploader as fb
        results['facebook'] = fb.upload(video_path, title, description)
    if "instagram" in PLATFORMS:
        if INSTAGRAM_PROVIDER == "graph_api":
            from .instagram import graph_api as ig
        elif INSTAGRAM_PROVIDER == "instagrapi":
            from .instagram import instagrapi_uploader as ig
        else:
            from .instagram import selenium_uploader as ig
        results['instagram'] = ig.upload(video_path, title, description)
    return results
'''

files["uploaders/youtube/__init__.py"] = ""
files["uploaders/youtube/internal_uploader.py"] = '''def upload(video_path, title, description):
    print(f"📤 YouTube Upload: {title}")
    print(f"   Video: {video_path}")
    return "YouTube Upload Success (Placeholder)"
'''

files["uploaders/facebook/__init__.py"] = ""
files["uploaders/facebook/selenium_uploader.py"] = '''def upload(video_path, title, description):
    print(f"📤 Facebook Upload: {title}")
    print(f"   Video: {video_path}")
    return "Facebook Upload Success (Placeholder)"
'''

files["uploaders/instagram/__init__.py"] = ""
files["uploaders/instagram/instagrapi_uploader.py"] = '''import os
from instagrapi import Client

def upload(video_path, title, description):
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    if not username or not password:
        print("⚠️ Instagram credentials not set. Skipping upload.")
        return "Instagram Upload Skipped (No Credentials)"
    cl = Client()
    cl.login(username, password)
    cl.clip_upload(video_path, caption=title + "\\n\\n" + description)
    return "Instagram Upload Success"
'''

files["uploaders/instagram/selenium_uploader.py"] = '''def upload(video_path, title, description):
    print(f"📤 Instagram Upload: {title}")
    print(f"   Video: {video_path}")
    return "Instagram Upload Success (Selenium Placeholder)"
'''

# ================================================================
#  CREATE FOLDERS AND FILES
# ================================================================

# Create root project folder
os.makedirs(PROJECT_NAME, exist_ok=True)
os.chdir(PROJECT_NAME)

# Create all folders
for folder in folders:
    os.makedirs(folder, exist_ok=True)

# Create all files
for file_path, content in files.items():
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Created: {file_path}")

print(f"""
╔══════════════════════════════════════════════════════╗
║      ✅ PROJECT CREATED SUCCESSFULLY!              ║
╚══════════════════════════════════════════════════════╝

📁 Folder: {PROJECT_NAME}/
📄 Total files created: {len(files)}

🚀 NEXT STEPS:
1. cd {PROJECT_NAME}
2. pip install -r requirements.txt
3. python main.py
""")