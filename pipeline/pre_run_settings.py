import json
import re
from datetime import datetime
from pathlib import Path

CONFIG_STATE_PATH = Path(__file__).resolve().parent.parent / "config_state.json"

CAPTION_STYLES = [
    "simple",
    "mozi",
    "karaoke",
    "beasty",
    "highlighter",
    "blur_switch",
    "grow",
    "glitch",
    "popline",
    "bottom_bold",
]


def load_config_state():
    if CONFIG_STATE_PATH.is_file():
        try:
            state_data = json.loads(CONFIG_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(state_data, dict):
                return state_data
        except Exception as e:
            print(f"[WARNING] Could not load config_state.json: {e}")
    return {}


def save_config_state(settings: dict):
    music_vol = settings.get("music_volume", 0.15)
    try:
        music_vol = float(music_vol)
    except (ValueError, TypeError):
        music_vol = 0.15

    state_data = {
        "aspect_ratio": settings.get("aspect_ratio", "9:16"),
        "duration": int(settings.get("duration", settings.get("duration_target", 15))),
        "music_volume": round(music_vol, 2),
        "tts_rate": settings.get("tts_rate", "+0%"),
        "tts_pitch": settings.get("tts_pitch", "+0Hz"),
        "caption_style": settings.get("caption_style", "bottom_bold"),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        CONFIG_STATE_PATH.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
        print("[INFO] Settings saved to config_state.json")
    except OSError as e:
        print(f"[WARNING] Could not save config_state.json: {e}")


def show_settings_menu(current_settings: dict) -> dict:
    settings = dict(current_settings)

    while True:
        aspect_ratio = settings.get("aspect_ratio", "9:16")
        duration = settings.get("duration", settings.get("duration_target", 15))
        music_vol = float(settings.get("music_volume", 0.15))
        music_pct = int(round(music_vol * 100))
        tts_rate = settings.get("tts_rate", "+0%")
        tts_pitch = settings.get("tts_pitch", "+0Hz")
        caption_style = settings.get("caption_style", "bottom_bold")

        print("\n==========================================")
        print("         PRE-RUN SETTINGS MENU            ")
        print("==========================================")
        print(f"[1] Aspect Ratio          : {aspect_ratio}")
        print(f"[2] Duration              : {duration} sec")
        print(f"[3] Background Music Vol  : {music_pct}% ({music_vol:.2f})")
        print(f"[4] TTS Rate              : {tts_rate}")
        print(f"[5] TTS Pitch             : {tts_pitch}")
        print(f"[6] Caption Style         : {caption_style}")
        print("[Enter] Confirm & Run Pipeline")
        print("==========================================")

        try:
            choice = input("Select option (1-6) or press Enter to run: ").strip()
        except EOFError:
            choice = ""

        if choice == "":
            save_config_state(settings)
            return settings

        if choice == "1":
            val = input("Enter Aspect Ratio (e.g. 9:16, 12:16, 14:16, 1:1, 4:5): ").strip()
            if re.fullmatch(r"\d+:\d+", val):
                settings["aspect_ratio"] = val
                print(f"[OK] Aspect Ratio set to {val}")
            else:
                print("[ERROR] Invalid aspect ratio format.")
        elif choice == "2":
            val = input("Enter Duration in seconds (12-25): ").strip()
            if val.isdigit() and 12 <= int(val) <= 25:
                dur = int(val)
                settings["duration"] = dur
                settings["duration_target"] = dur
                print(f"[OK] Duration set to {dur} sec")
            else:
                print("[ERROR] Invalid duration. Enter an integer between 12 and 25.")
        elif choice == "3":
            val = input("Enter Background Music Volume % (0-100, e.g. 20, 50, 80): ").strip().rstrip("%")
            try:
                pct = float(val)
                if 0 <= pct <= 100:
                    vol = round(pct / 100.0, 2)
                    settings["music_volume"] = vol
                    print(f"[OK] Background Music Volume set to {int(pct)}% ({vol})")
                else:
                    print("[ERROR] Volume percentage must be between 0 and 100.")
            except ValueError:
                print("[ERROR] Invalid percentage input.")
        elif choice == "4":
            val = input("Enter TTS Rate (e.g. +0%, +10%, -5%): ").strip()
            if re.fullmatch(r"[+-]\d+%", val):
                settings["tts_rate"] = val
                print(f"[OK] TTS Rate set to {val}")
            else:
                print("[ERROR] Invalid TTS rate format. Use signed percentage like +0% or +10%.")
        elif choice == "5":
            val = input("Enter TTS Pitch (e.g. +0Hz, +2Hz, -2Hz): ").strip()
            if re.fullmatch(r"[+-]\d+Hz", val):
                settings["tts_pitch"] = val
                print(f"[OK] TTS Pitch set to {val}")
            else:
                print("[ERROR] Invalid TTS pitch format. Use signed Hz like +0Hz or +2Hz.")
        elif choice == "6":
            print("\nSelect Caption Style:")
            print("[1]  simple       - White text, black border, no box")
            print("[2]  mozi         - White text with green highlight, rounded box")
            print("[3]  karaoke      - Word-by-word highlight (yellow)")
            print("[4]  beasty       - Bold white text, black outline")
            print("[5]  highlighter  - Yellow highlighted background, black text")
            print("[6]  blur_switch  - White bold text with dark background box")
            print("[7]  grow         - Text grows/bolds at line start")
            print("[8]  glitch       - White text with cyan/magenta chromatic offset")
            print("[9]  popline      - White text with accent underline")
            print("[10] bottom_bold - White bold text, bottom center")
            val = input("Enter choice (1-10 or style name): ").strip().lower()
            if val.isdigit() and 1 <= int(val) <= len(CAPTION_STYLES):
                selected = CAPTION_STYLES[int(val) - 1]
                settings["caption_style"] = selected
                print(f"[OK] Caption Style set to '{selected}'")
            elif val in CAPTION_STYLES:
                settings["caption_style"] = val
                print(f"[OK] Caption Style set to '{val}'")
            else:
                print("[ERROR] Invalid style selection.")
        else:
            print("[ERROR] Please select 1-6 or press Enter.")
