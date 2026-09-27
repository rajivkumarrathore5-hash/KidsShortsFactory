import os
import runpy
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_SECRETS_PATH = Path(__file__).resolve().with_name("secrets.py")
try:
	_LOCAL_SECRETS = runpy.run_path(str(_SECRETS_PATH))
except FileNotFoundError:
	_LOCAL_SECRETS = {}


def get_secret(name, default=""):
	env_val = os.getenv(name)
	if env_val:
		return env_val
	return _LOCAL_SECRETS.get(name, default)


# ================================================================
#  SYSTEM CONFIGURATION - KIDS SHORTS FACTORY
# ================================================================

# ------ PLATFORMS TO UPLOAD ------
PLATFORMS = ["youtube", "facebook", "instagram"]
ENABLE_UPLOAD = os.getenv("ENABLE_UPLOAD", "false").strip().lower() in {
	"1", "true", "yes", "on"
}
ASPECT_RATIO = os.getenv("ASPECT_RATIO", "9:16")
TTS_VOICE = "indicf5"
TTS_PROVIDER = "indicf5"
TTS_PITCH = os.getenv("TTS_PITCH", "+0Hz")
TTS_RATE = os.getenv("TTS_RATE", "+0%")

INDICF5_REFERENCE_AUDIO = os.getenv(
	"INDICF5_REFERENCE_AUDIO",
	r"C:\Users\91757\Downloads\KidsShortsFactory\input\kid_voice.wav",
)
INDICF5_REFERENCE_TEXT = os.getenv(
	"INDICF5_REFERENCE_TEXT",
	r"C:\Users\91757\Downloads\KidsShortsFactory\input\kid_voice.txt",
)
INDICF5_SPEED = float(os.getenv("INDICF5_SPEED", "1.25"))
INDICF5_SERVER_URL = os.getenv(
	"INDICF5_SERVER_URL", "http://127.0.0.1:8765"
)
INDICF5_SERVER_DIR = os.getenv(
	"INDICF5_SERVER_DIR",
	r"C:\Users\91757\Downloads\movie_explainer_5\indicf5_test",
)
INDICF5_SERVER_SCRIPT = os.getenv(
	"INDICF5_SERVER_SCRIPT",
	r"C:\Users\91757\Downloads\movie_explainer_5\indicf5_test\indicf5_server.py",
)
INDICF5_SERVER_PYTHON = os.getenv(
	"INDICF5_SERVER_PYTHON",
	r"C:\Users\91757\Downloads\movie_explainer_5\indicf5_test\.venv\Scripts\python.exe",
)
CHARACTER = os.getenv("CHARACTER", "Krishna")
THEME = os.getenv("THEME", "Devotion")
DURATION_TARGET = int(os.getenv("DURATION_TARGET", "15"))
CAPTION_MODE = os.getenv("CAPTION_MODE", "line_by_line").strip().lower()
FONT_PATH = os.getenv("FONT_PATH", "assets/fonts/NotoSansDevanagari-Regular.ttf")
CAPTION_FONT_SIZE = int(os.getenv("CAPTION_FONT_SIZE", "48"))
CAPTION_COLOR = os.getenv("CAPTION_COLOR", "white")
CAPTION_BORDER_WIDTH = int(os.getenv("CAPTION_BORDER_WIDTH", "2"))
CAPTION_BORDER_COLOR = os.getenv("CAPTION_BORDER_COLOR", "black")
SCENE_TRANSITION = os.getenv("SCENE_TRANSITION", "fade").strip().lower()
SCENE_TRANSITION_DURATION = float(os.getenv("SCENE_TRANSITION_DURATION", "0.4"))
KEN_BURNS_ENABLED = os.getenv("KEN_BURNS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
KEN_BURNS_ZOOM = float(os.getenv("KEN_BURNS_ZOOM", "1.05"))
MIN_SCENE_DURATION = float(os.getenv("MIN_SCENE_DURATION", "3"))

MAX_SCENE_DURATION = float(os.getenv("MAX_SCENE_DURATION", "5"))
BACKGROUND_MUSIC = os.getenv("BACKGROUND_MUSIC", "true").strip().lower() in {"1", "true", "yes", "on"}
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.15"))
INTRO_ENABLED = os.getenv("INTRO_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
OUTRO_ENABLED = os.getenv("OUTRO_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Kids Shorts Factory")
MIN_DURATION = int(os.getenv("MIN_DURATION", "12"))
MAX_DURATION = int(os.getenv("MAX_DURATION", "25"))
VISUAL_SOURCE = os.getenv("VISUAL_SOURCE", "ai").strip().lower()
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "agnes").strip().lower()
AI_IMAGE_PROVIDER = IMAGE_PROVIDER
CLOUDFLARE_MODEL = os.getenv("CLOUDFLARE_MODEL", "@cf/black-forest-labs/flux-1-schnell").strip()
AI_IMAGE_SEED_PER_VIDEO = os.getenv("AI_IMAGE_SEED_PER_VIDEO", "true").strip().lower() in {"1", "true", "yes", "on"}

THEME_HISTORY_SIZE = int(os.getenv("THEME_HISTORY_SIZE", "10"))
DYNAMIC_MUSIC = os.getenv("DYNAMIC_MUSIC", "true").strip().lower() in {"1", "true", "yes", "on"}
RANDOM_STYLE = os.getenv("RANDOM_STYLE", "true").strip().lower() in {"1", "true", "yes", "on"}
CLEANUP_TEMP_FILES = os.getenv("CLEANUP_TEMP_FILES", "true").strip().lower() in {"1", "true", "yes", "on"}
RANDOM_EFFECTS = os.getenv("RANDOM_EFFECTS", "true").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_TRANSITION = os.getenv("DEFAULT_TRANSITION", "fade").strip().lower()


_raw_gemini_chain = get_secret(
	"GEMINI_MODEL_CHAIN",
	"gemini-3.8-flash,gemini-3.5-flash,gemini-3.1-flash-lite",
)
GEMINI_MODEL_CHAIN = [m.strip() for m in _raw_gemini_chain.split(",") if m.strip()]

_raw_groq_chain = get_secret(
	"GROQ_MODEL_CHAIN",
	"openai/gpt-oss-20b,openai/gpt-oss-120b",
)
GROQ_MODEL_CHAIN = [m.strip() for m in _raw_groq_chain.split(",") if m.strip()]

_raw_openrouter_chain = get_secret(
	"OPENROUTER_MODEL_CHAIN",
	"openrouter/free,qwen/qwen3-coder:free,deepseek/deepseek-r1:free",
)
OPENROUTER_MODEL_CHAIN = [m.strip() for m in _raw_openrouter_chain.split(",") if m.strip()]

# ------ SCRIPT GENERATOR (Options: "gemini", "groq") ------


SCRIPT_PROVIDER = "gemini"

# ------ TEXT-TO-SPEECH (Options: "edge", "coqui") ------

# ------ VISUALS (Options: "pexels", "pixabay") ------
VISUAL_PROVIDER = "pexels"

# ------ VIDEO RENDER ENGINE (FFmpeg-based options) ------
RENDER_ENGINE = "simple"

# ------ UPLOADERS ------
YOUTUBE_PROVIDER = "api"
FACEBOOK_PROVIDER = "selenium"
INSTAGRAM_PROVIDER = "instagrapi"

# ------ VIDEO SETTINGS ------
SHORT_DURATION = DURATION_TARGET

# ------ SCHEDULING ------
UPLOAD_INTERVAL_HOURS = 9

# ------ FALLBACK STRATEGY ------
FALLBACK_ENABLED = True

# ================================================================
#  PRINT CONFIGURATION
# ================================================================

print(f"""
========================================================
			 KIDS SHORTS FACTORY v2.0
		 Duration: {SHORT_DURATION} sec | Ratio: {ASPECT_RATIO}
		 TTS: {TTS_PROVIDER.upper()}
		 Script: {SCRIPT_PROVIDER.upper()}
		 Visuals: {VISUAL_PROVIDER.upper()}
		 Platforms: {', '.join(PLATFORMS)}
========================================================
""")