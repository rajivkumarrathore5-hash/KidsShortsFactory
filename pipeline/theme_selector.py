import json
import os
import random
import re
import tempfile
from datetime import datetime
from pathlib import Path

from config import RANDOM_STYLE, THEME_HISTORY_SIZE


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THEMES_PATH = PROJECT_ROOT / "data" / "themes.json"
HISTORY_PATH = PROJECT_ROOT / "data" / "theme_history.json"
STYLE_VARIANTS = [
    "cinematic devotional art, rich warm light, detailed vertical composition",
    "stylized 3D animated family-film look, expressive faces, colorful vertical composition",
    "traditional Madhubani painting, intricate Indian folk patterns, vertical composition",
    "soft watercolor devotional illustration, delicate paper texture, vertical composition",
    "hyperrealistic devotional art, dramatic lighting, detailed vertical composition",
]


def _load_themes():
    with THEMES_PATH.open(encoding="utf-8") as themes_file:
        themes = json.load(themes_file)
    if not isinstance(themes, list) or len(themes) < 30:
        raise ValueError(f"{THEMES_PATH} must contain at least 30 theme entries.")
    required = {"id", "character", "theme", "mood", "setting", "base_style", "keywords", "visual_style", "music_track", "music_prompt", "voice"}
    for theme in themes:
        missing = required.difference(theme)
        if missing:
            raise ValueError(f"Theme {theme.get('id', '<unknown>')} is missing keys: {sorted(missing)}")
    return themes


def _load_history():
    if not HISTORY_PATH.is_file():
        return []
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return history if isinstance(history, list) else []


def _save_history(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=HISTORY_PATH.parent,
            suffix=".tmp", delete=False,
        ) as history_file:
            json.dump(history, history_file, ensure_ascii=False, indent=2)
            history_file.write("\n")
            temporary_path = Path(history_file.name)
        os.replace(temporary_path, HISTORY_PATH)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


# Ordered (keywords, group) rules. Each god gets its own group so that every
# god has an equal chance of being picked. Order matters for combined
# characters (e.g. "Ram and Hanuman" -> Hanuman, "Shiv and Parvati" -> Shiv).
GOD_GROUP_RULES = [
    (("jagannath",), "Jagannath"),
    (("khatu", "shyam"), "Khatu Shyam"),
    (("hanuman",), "Hanuman"),
    (("ganesh",), "Ganesh"),
    (("kartikeya", "murugan"), "Kartikeya"),
    (("mahakal",), "Mahakal"),
    (("kedarnath",), "Kedarnath"),
    (("mallikarjuna",), "Mallikarjuna"),
    (("shiv",), "Shiv"),
    (("parvati", "gauri"), "Parvati"),
    (("durga",), "Durga"),
    (("kali",), "Kali"),
    (("chamundeshwari",), "Chamundeshwari"),
    (("kamakhya",), "Kamakhya"),
    (("meenakshi",), "Meenakshi"),
    (("vaishno",), "Vaishno Devi"),
    (("lakshmi",), "Lakshmi"),
    (("saraswati",), "Saraswati"),
    (("ganga",), "Ganga"),
    (("narasimha",), "Narasimha"),
    (("dashavatar",), "Dashavatar"),
    (("vishnu",), "Vishnu"),
    (("balaji", "venkateshwara", "tirupati"), "Tirupati Balaji"),
    (("ram", "sita"), "Ram-Sita"),
    (("krishna", "radha"), "Krishna"),
    (("shani",), "Shani Dev"),
    (("sai",), "Sai Baba"),
    (("ayyappa",), "Ayyappa"),
    (("vitthal", "vithoba"), "Vitthal"),
    (("surya",), "Surya Dev"),
    (("khandoba",), "Khandoba"),
]


def _theme_group(theme):
    words = set(re.findall(r"[a-z]+", theme["character"].casefold()))
    for keywords, group in GOD_GROUP_RULES:
        if any(keyword in words for keyword in keywords):
            return group
    return "General devotional"


def pick_random_duration(min_duration, max_duration):
    if min_duration > max_duration:
        raise ValueError("MIN_DURATION cannot exceed MAX_DURATION.")
    history = _load_history()
    recent_durations = {
        entry.get("duration")
        for entry in history[-4:]
        if isinstance(entry.get("duration"), int)
    }
    available = [
        duration for duration in range(min_duration, max_duration + 1)
        if duration not in recent_durations
    ]
    return random.choice(available or list(range(min_duration, max_duration + 1)))


def pick_random_theme(duration_seconds=None):
    themes = _load_themes()
    history = _load_history()
    history_size = max(0, int(THEME_HISTORY_SIZE))
    recent_ids = {entry.get("id") for entry in history[-history_size:]} if history_size else set()
    recent_groups = {entry.get("group") for entry in history[-4:]}
    recent_styles = {entry.get("visual_style") for entry in history[-4:]}
    recent_music = {entry.get("music_track") for entry in history[-4:]}
    available = [theme for theme in themes if theme["id"] not in recent_ids]
    if not available:
        available = themes

    fresh_groups = {_theme_group(theme) for theme in available}.difference(recent_groups)
    if fresh_groups:
        available = [theme for theme in available if _theme_group(theme) in fresh_groups]
    fresh_music = [theme for theme in available if theme["music_track"] not in recent_music]
    if fresh_music:
        available = fresh_music

    selected = dict(random.choice(available))
    group = _theme_group(selected)
    if RANDOM_STYLE:
        fresh_styles = [style for style in STYLE_VARIANTS if style not in recent_styles]
        selected["visual_style"] = random.choice(fresh_styles or STYLE_VARIANTS)

    history.append(
        {
            "id": selected["id"],
            "group": group,
            "visual_style": selected["visual_style"],
            "music_track": selected["music_track"],
            "duration": duration_seconds,
            "selected_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _save_history(history[-history_size:] if history_size else [])
    return selected
