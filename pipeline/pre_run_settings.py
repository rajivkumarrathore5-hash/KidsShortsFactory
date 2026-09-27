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
    existing_state = load_config_state()
    music_vol = settings.get("music_volume", 0.15)
    try:
        music_vol = float(music_vol)
    except (ValueError, TypeError):
        music_vol = 0.15

    state_data = {
        **existing_state,
        "video_mode": settings.get("video_mode", "short"),
        "aspect_ratio": settings.get("aspect_ratio", "9:16"),
        "duration": int(settings.get("duration", settings.get("duration_target", 15))),
        "music_volume": round(music_vol, 2),
        "tts_rate": settings.get("tts_rate", "+0%"),
        "tts_pitch": settings.get("tts_pitch", "+0Hz"),
        "caption_style": settings.get("caption_style", "bottom_bold"),
        "brightness": int(settings.get("brightness", 0)),
        "contrast": int(settings.get("contrast", 0)),
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
        video_mode = settings.get("video_mode", "short")
        aspect_ratio = settings.get("aspect_ratio", "9:16")
        duration = settings.get("duration", settings.get("duration_target", 20 if video_mode == "short" else 90))
        music_vol = float(settings.get("music_volume", 0.15))
        music_pct = int(round(music_vol * 100))
        tts_rate = settings.get("tts_rate", "+0%")
        tts_pitch = settings.get("tts_pitch", "+0Hz")
        caption_style = settings.get("caption_style", "bottom_bold")
        brightness = int(settings.get("brightness", 0))
        contrast = int(settings.get("contrast", 0))

        print("\n==========================================")
        print("         PRE-RUN SETTINGS MENU            ")
        print("==========================================")
        print(f"[1] Video Mode            : {video_mode}")
        print(f"[2] Aspect Ratio          : {aspect_ratio}")
        print(f"[3] Duration              : {duration} sec")
        print(f"[4] Background Music Vol  : {music_pct}% ({music_vol:.2f})")
        print(f"[5] TTS Rate              : {tts_rate}")
        print(f"[6] TTS Pitch             : {tts_pitch}")
        print(f"[7] Caption Style         : {caption_style}")
        print(f"[8] Brightness            : {brightness}%")
        print(f"[9] Contrast              : {contrast}%")
        print("[Enter] Confirm & Run Pipeline")
        print("==========================================")

        try:
            choice = input("Select option (1-9) or press Enter to run: ").strip()
        except EOFError:
            choice = ""

        if choice == "":
            save_config_state(settings)
            return settings

        if choice == "1":
            print("\nSelect Video Mode:")
            print("[1] short - 15 to 30 seconds, simple script")
            print("[2] story - 60 to 180 seconds, full story (hook + setup + story + twist + moral + CTA)")
            val = input("Enter choice (1-2): ").strip().lower()
            old_mode = settings.get("video_mode", "short")
            new_mode = None
            if val in ("1", "short"):
                new_mode = "short"
            elif val in ("2", "story"):
                new_mode = "story"
            else:
                print("[ERROR] Invalid choice. Select 1 or 2.")

            if new_mode and new_mode != old_mode:
                settings["video_mode"] = new_mode
                print(f"[OK] Video Mode set to '{new_mode}'")
                # Mode switching duration reset rules (FIX 5)
                if new_mode == "short":
                    settings["duration"] = 20
                    settings["duration_target"] = 20
                    print("[INFO] Duration reset to default for short mode: 20 sec")
                elif new_mode == "story":
                    settings["duration"] = 90
                    settings["duration_target"] = 90
                    print("[INFO] Duration reset to default for story mode: 90 sec")
            elif new_mode:
                print(f"[OK] Video Mode remains '{new_mode}'")

        elif choice == "2":
            val = input("Enter Aspect Ratio (e.g. 9:16, 12:16, 14:16, 1:1, 4:5): ").strip()
            if re.fullmatch(r"\d+:\d+", val):
                settings["aspect_ratio"] = val
                print(f"[OK] Aspect Ratio set to {val}")
            else:
                print("[ERROR] Invalid aspect ratio format.")

        elif choice == "3":
            current_mode = settings.get("video_mode", "short")
            min_d, max_d = (15, 30) if current_mode == "short" else (60, 180)
            val = input(f"Enter Duration in seconds ({min_d}-{max_d}): ").strip()
            if val.isdigit() and min_d <= int(val) <= max_d:
                dur = int(val)
                settings["duration"] = dur
                settings["duration_target"] = dur
                print(f"[OK] Duration set to {dur} sec")
            else:
                print(f"[ERROR] Invalid duration. Enter an integer between {min_d} and {max_d}.")

        elif choice == "4":
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

        elif choice == "5":
            val = input("Enter TTS Rate (e.g. +0%, +10%, -5%): ").strip()
            if re.fullmatch(r"[+-]\d+%", val):
                settings["tts_rate"] = val
                print(f"[OK] TTS Rate set to {val}")
            else:
                print("[ERROR] Invalid TTS rate format. Use signed percentage like +0% or +10%.")

        elif choice == "6":
            val = input("Enter TTS Pitch (e.g. +0Hz, +2Hz, -2Hz): ").strip()
            if re.fullmatch(r"[+-]\d+Hz", val):
                settings["tts_pitch"] = val
                print(f"[OK] TTS Pitch set to {val}")
            else:
                print("[ERROR] Invalid TTS pitch format. Use signed Hz like +0Hz or +2Hz.")

        elif choice == "7":
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

        elif choice == "8":
            val = input("Enter Brightness percentage (-50 to +50, e.g. 0, 10, -10): ").strip().rstrip("%")
            try:
                b_val = int(val)
                if -50 <= b_val <= 50:
                    settings["brightness"] = b_val
                    print(f"[OK] Brightness set to {b_val}%")
                else:
                    print("[ERROR] Brightness must be between -50% and +50%.")
            except ValueError:
                print("[ERROR] Invalid integer input.")

        elif choice == "9":
            val = input("Enter Contrast percentage (-50 to +50, e.g. 0, 10, -10): ").strip().rstrip("%")
            try:
                c_val = int(val)
                if -50 <= c_val <= 50:
                    settings["contrast"] = c_val
                    print(f"[OK] Contrast set to {c_val}%")
                else:
                    print("[ERROR] Contrast must be between -50% and +50%.")
            except ValueError:
                print("[ERROR] Invalid integer input.")

        else:
            print("[ERROR] Please select 1-9 or press Enter.")

