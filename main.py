import argparse
import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from script_gen.factory import get_script
from script_gen.history import get_script_metadata, spoken_text
from pipeline.theme_selector import (
    _load_themes,
    _theme_group,
    pick_random_duration,
    pick_random_theme,
)
from pipeline.visuals import get_scene_images
from pipeline.effects import pick_random_effects
from pipeline.pre_run_settings import (
    load_config_state,
    save_config_state,
    show_settings_menu,
)
from tts.factory import get_tts
from video_engine.factory import get_render_engine
from video_engine.simple_engine import (
    allocate_scene_durations,
    get_audio_duration,
    get_video_info,
    resolution_for_aspect_ratio,
)
from config import (
    ASPECT_RATIO,
    BACKGROUND_MUSIC,
    CAPTION_BORDER_COLOR,
    CAPTION_BORDER_WIDTH,
    CAPTION_COLOR,
    CAPTION_FONT_SIZE,
    CAPTION_MODE,
    CHANNEL_NAME,
    CHARACTER,
    DURATION_TARGET,
    DYNAMIC_MUSIC,
    ENABLE_UPLOAD,
    FONT_PATH,
    INDICF5_REFERENCE_AUDIO,
    INDICF5_REFERENCE_TEXT,
    INDICF5_SPEED,
    IMAGE_PROVIDER,
    AI_IMAGE_PROVIDER,
    AI_IMAGE_SEED_PER_VIDEO,
    INTRO_ENABLED,
    KEN_BURNS_ENABLED,
    KEN_BURNS_ZOOM,
    MAX_SCENE_DURATION,
    MIN_SCENE_DURATION,
    MUSIC_VOLUME,
    MAX_DURATION,
    MIN_DURATION,
    OUTRO_ENABLED,
    SCENE_TRANSITION,
    SCENE_TRANSITION_DURATION,
    THEME,
    TTS_PITCH,
    TTS_PROVIDER,
    TTS_RATE,
    TTS_VOICE,
    VISUAL_SOURCE,
    CLEANUP_TEMP_FILES,
    RANDOM_EFFECTS,
    DEFAULT_TRANSITION,
)

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

APPROVAL_PROMPT = (
    "Kya yeh video sahi hai? [y] Accept / [u] Upload Now / [n] Reject & Regenerate / [q] Quit"
)



def _default_settings():
    return {
        "aspect_ratio": ASPECT_RATIO,
        "tts_voice": TTS_VOICE,
        "tts_provider": "indicf5",
        "tts_pitch": TTS_PITCH,
        "tts_rate": TTS_RATE,
        "indicf5_reference_audio": INDICF5_REFERENCE_AUDIO,
        "indicf5_reference_text": INDICF5_REFERENCE_TEXT,
        "indicf5_speed": INDICF5_SPEED,
        "theme_config": None,
        "scene_count": 4,
        "image_seed": None,
        "visual_source": VISUAL_SOURCE,
        "image_provider": IMAGE_PROVIDER,
        "ai_image_provider": IMAGE_PROVIDER,
        "dynamic_music": DYNAMIC_MUSIC,

        "character": CHARACTER,
        "theme": THEME,
        "duration_target": DURATION_TARGET,
        "caption_mode": CAPTION_MODE,
        "font_path": FONT_PATH,
        "caption_font_size": CAPTION_FONT_SIZE,
        "caption_color": CAPTION_COLOR,
        "caption_border_width": CAPTION_BORDER_WIDTH,
        "caption_border_color": CAPTION_BORDER_COLOR,
        "scene_transition": SCENE_TRANSITION,
        "scene_transition_duration": SCENE_TRANSITION_DURATION,
        "ken_burns_enabled": KEN_BURNS_ENABLED,
        "ken_burns_zoom": KEN_BURNS_ZOOM,
        "min_scene_duration": MIN_SCENE_DURATION,
        "max_scene_duration": MAX_SCENE_DURATION,
        "background_music": BACKGROUND_MUSIC,
        "music_volume": MUSIC_VOLUME,
        "intro_enabled": INTRO_ENABLED,
        "outro_enabled": OUTRO_ENABLED,
        "channel_name": CHANNEL_NAME,
        "cleanup_temp_files": CLEANUP_TEMP_FILES,
        "caption_style": "bottom_bold",
        "brightness": 0,
        "contrast": 0,
    }



def _merge_settings(runtime_overrides):
    settings = {**_default_settings(), **runtime_overrides}
    settings["tts_provider"] = "indicf5"
    resolution_for_aspect_ratio(settings["aspect_ratio"])
    if not re.fullmatch(r"[+-]\d+Hz", settings["tts_pitch"]):
        raise ValueError(f"Invalid TTS pitch: {settings['tts_pitch']}")
    if not re.fullmatch(r"[+-]\d+%", settings["tts_rate"]):
        raise ValueError(f"Invalid TTS rate: {settings['tts_rate']}")
    if not MIN_DURATION <= int(settings["duration_target"]) <= MAX_DURATION:
        raise ValueError(f"Duration target must be between {MIN_DURATION} and {MAX_DURATION} seconds.")
    if settings["caption_mode"] not in {"line_by_line", "full"}:
        raise ValueError("CAPTION_MODE must be 'line_by_line' or 'full'.")
    if int(settings["caption_font_size"]) <= 0:
        raise ValueError("Caption font size must be positive.")
    if int(settings["caption_border_width"]) < 0:
        raise ValueError("Caption border width cannot be negative.")
    if settings["scene_transition"] not in {"none", "fade"}:
        raise ValueError("SCENE_TRANSITION must be 'none' or 'fade'.")
    if float(settings["scene_transition_duration"]) < 0:
        raise ValueError("Scene transition duration cannot be negative.")
    if float(settings["ken_burns_zoom"]) < 1.0:
        raise ValueError("KEN_BURNS_ZOOM must be at least 1.0.")
    if float(settings["min_scene_duration"]) <= 0:
        raise ValueError("MIN_SCENE_DURATION must be positive.")
    if float(settings["max_scene_duration"]) < float(settings["min_scene_duration"]):
        raise ValueError("MAX_SCENE_DURATION must be at least MIN_SCENE_DURATION.")
    if not 0.0 <= float(settings["music_volume"]) <= 1.0:
        raise ValueError("MUSIC_VOLUME must be between 0 and 1.")
    if not 0.5 <= float(settings["indicf5_speed"]) <= 2.0:
        raise ValueError("INDICF5_SPEED must be between 0.5 and 2.0.")
    settings["duration_target"] = int(settings["duration_target"])
    settings["caption_font_size"] = int(settings["caption_font_size"])
    settings["caption_border_width"] = int(settings["caption_border_width"])
    return settings


def _display_character(character):
    return character.removeprefix("Bal ") if character else "Unknown"


def _generate_script(settings):
    theme_config = settings["theme_config"]
    return get_script(
        character=settings["character"],
        theme=settings["theme"],
        duration=settings["duration_target"],
        theme_config=theme_config,
        scene_count=settings["scene_count"],
    )


def _determine_voice_for_theme(theme_config):
    """
    Reads the theme's voice field from data/themes.json (defaults to indicf5).
    """
    theme_id = theme_config.get("id", "unknown") if theme_config else "default"
    voice = theme_config.get("voice", "indicf5") if theme_config else "indicf5"
    print(f"[INFO] Voice: {voice} (from theme: {theme_id})")
    return voice


def calculate_scene_count(duration: int) -> int:
    duration = int(duration)
    if duration <= 20:
        return 3
    elif duration <= 30:
        return 4
    elif duration <= 45:
        return 5
    elif duration <= 60:
        return 6
    elif duration <= 90:
        return 8
    elif duration <= 120:
        return 10
    elif duration <= 150:
        return 12
    else:
        return 15


def _select_dynamic_job(settings, character_override=None, duration_override=None):
    if duration_override is not None:
        duration = int(duration_override)
        if not MIN_DURATION <= duration <= MAX_DURATION:
            raise ValueError(f"Duration target must be between {MIN_DURATION} and {MAX_DURATION} seconds.")
        print(f"[INFO] Duration: {duration} sec")
    else:
        duration = pick_random_duration(MIN_DURATION, MAX_DURATION)

    if character_override and character_override.strip().casefold() != "random":
        char_query = character_override.strip().casefold()
        themes = _load_themes()
        matched = [
            t for t in themes
            if char_query in t["character"].casefold()
            or char_query in t["id"].casefold()
            or char_query in _theme_group(t).casefold()
        ]
        if matched:
            theme_config = dict(random.choice(matched))
            print(f"[INFO] Character override: {character_override} (selected theme: {theme_config['id']})")
        else:
            print(f"[WARNING] No themes match character '{character_override}'. Selecting random theme.")
            theme_config = pick_random_theme(duration_seconds=duration)
    else:
        theme_config = pick_random_theme(duration_seconds=duration)

    if not theme_config:
        raise ValueError("Theme selection returned None configuration.")

    scene_count = calculate_scene_count(duration)

    image_seed = random.randint(0, 2**31 - 1) if AI_IMAGE_SEED_PER_VIDEO else None
    indicf5_speed = INDICF5_SPEED
    settings.update(
        {
            "theme_config": theme_config,
            "character": theme_config["character"],
            "theme": theme_config["theme"],
            "visual_style": theme_config["visual_style"],
            "music_track": theme_config["music_track"],
            "music_prompt": theme_config.get("music_prompt"),
            "duration_target": duration,
            "scene_count": scene_count,
            "image_seed": image_seed,
            "indicf5_speed": indicf5_speed,
        }
    )
    print(
        f"[1/7] Theme selected: {theme_config['id']} "
        f"({theme_config['theme']}; {theme_config['character']}; "
        f"style: {theme_config['visual_style']})"
    )
    print(f"[2/7] Duration: {duration} sec, Scenes: {scene_count}")
    return theme_config


def _render_video(script, settings):
    narration_text = spoken_text(script)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    audio_path = os.path.join(OUTPUT_DIR, f"audio_{timestamp}.wav")
    boundaries_path = f"{audio_path}.boundaries.json"
    video_path = os.path.join(OUTPUT_DIR, f"short_{timestamp}.mp4")

    scenes = script["scenes"]
    theme_config = settings["theme_config"]
    if not theme_config:
        raise ValueError("Theme configuration is None. Cannot render video.")

    print(f"[3/7] Script generated (mood: {script['mood']})")

    visual_dir = os.path.join(OUTPUT_DIR, "temp_visuals", timestamp)
    provider_name = settings.get("image_provider", settings.get("ai_image_provider", "agnes"))
    visual_label = f"AI images ({provider_name})" if settings["visual_source"] == "ai" else "Pexels images"
    seed_label = f" (seed: {settings['image_seed']})" if settings["visual_source"] == "ai" else ""
    print(f"[4/7] Fetching {len(scenes)} {visual_label}{seed_label}...")
    image_paths = get_scene_images(
        scenes,
        visual_dir,
        theme_config,
        aspect_ratio=settings["aspect_ratio"],
        visual_source=settings["visual_source"],
        seed=settings["image_seed"],
        image_provider=provider_name,
    )


    def synthesize_voiceover():
        tts_func = get_tts(
            provider="indicf5",
            voice=settings["tts_voice"],
            pitch=settings["tts_pitch"],
            rate=settings["tts_rate"],
            ref_audio_path=settings["indicf5_reference_audio"],
            ref_text_path=settings["indicf5_reference_text"],
            speed=settings["indicf5_speed"],
        )
        tts_func(narration_text, audio_path)
        return get_audio_duration(audio_path)

    audio_duration = synthesize_voiceover()
    for attempt in range(2):
        target_duration = settings["duration_target"]
        if abs(audio_duration - target_duration) <= 0.6:
            break
        adjusted_speed = min(
            2.0,
            max(0.5, settings["indicf5_speed"] * audio_duration / target_duration),
        )
        if abs(adjusted_speed - settings["indicf5_speed"]) < 0.01:
            break
        print(
            f"[INFO] IndicF5 duration {audio_duration:.1f}s differs from "
            f"{target_duration}s target; adjusting speed to {adjusted_speed:.2f} "
            f"(retry {attempt + 1}/2)."
        )
        settings["indicf5_speed"] = adjusted_speed
        audio_duration = synthesize_voiceover()
    print(f"[5/7] Voiceover generated (indicf5, duration: {audio_duration:.1f} sec)")
    word_boundaries = None
    if os.path.isfile(boundaries_path):
        with open(boundaries_path, encoding="utf-8") as boundaries_file:
            word_boundaries = json.load(boundaries_file)

    scene_durations = allocate_scene_durations(
        scenes,
        audio_duration,
        min_duration=settings["min_scene_duration"],
        max_duration=settings["max_scene_duration"],
    )
    print("      Scene timings: " + ", ".join(f"{value:.1f}s" for value in scene_durations))
    selected_music = theme_config.get("music_track", "flute_soft.mp3")
    music_prompt = theme_config.get("music_prompt", "soft flute romantic devotional Indian classical gentle tabla")
    music_path = os.path.join("data", "music", selected_music)
    music_enabled = settings["dynamic_music"] and settings["background_music"]
    if music_enabled:
        print(f"[6/7] Dynamic music enabled (prompt: '{music_prompt}', volume: {settings['music_volume']:.2f})")
    render_engine = get_render_engine()
    render_label = "Ken Burns (zoom+pan+rotate) + transitions" if settings["ken_burns_enabled"] else "scene render"
    print(f"Rendering with {render_label}...")
    render_engine(
        audio_path,
        narration_text,
        video_path,
        duration=settings["duration_target"],
        image_paths=image_paths,
        aspect_ratio=settings["aspect_ratio"],
        word_boundaries=word_boundaries,
        caption_mode=settings["caption_mode"],
        font_path=settings["font_path"],
        caption_font_size=settings["caption_font_size"],
        caption_color=settings["caption_color"],
        caption_border_width=settings["caption_border_width"],
        caption_border_color=settings["caption_border_color"],
        scenes=scenes,
        scene_durations=scene_durations,
        ken_burns_enabled=settings["ken_burns_enabled"],
        ken_burns_zoom=settings["ken_burns_zoom"],
        scene_transition=settings["scene_transition"],
        scene_transition_duration=settings["scene_transition_duration"],
        music_path=music_path,
        music_prompt=music_prompt,
        music_volume=settings["music_volume"],
        background_music=music_enabled,
        intro_enabled=settings["intro_enabled"],
        outro_enabled=settings["outro_enabled"],
        channel_name=settings["channel_name"],
        effects=settings.get("effects"),
        caption_style=settings.get("caption_style"),
    )

    if not os.path.isfile(video_path) or os.path.getsize(video_path) == 0:
        raise RuntimeError("Renderer did not create a non-empty video file.")
    video_info = get_video_info(video_path)
    expected_resolution = resolution_for_aspect_ratio(settings["aspect_ratio"])
    if (video_info["width"], video_info["height"]) != expected_resolution:
        raise RuntimeError(
            "Rendered resolution does not match the selected aspect ratio: "
            f"expected {expected_resolution}, got "
            f"{video_info['width']}x{video_info['height']}"
        )
    print(f"[7/7] Video saved: {video_path}")
    _cleanup_pipeline_temp_files(audio_path=audio_path, boundaries_path=boundaries_path, settings=settings)
    return audio_path, boundaries_path, video_path, video_info


def _cleanup_pipeline_temp_files(audio_path=None, boundaries_path=None, settings=None):
    """
    Automatic cleanup step executed after final video is saved successfully:
    1. Delete all files in outputs/temp_visuals/ folder (keep the folder itself)
    2. Delete outputs/temp_music.mp3 if it exists
    3. Delete the intermediate audio_*.wav file (the one just created for this run)
    4. Keep ONLY the final short_*.mp4 file in outputs/
    5. Clean up any orphan TEMP_MPY_*.mp3 files in the project root
    Log format: [CLEANUP] Deleted outputs/temp_visuals/scene_1.jpg
    """
    should_cleanup = settings.get("cleanup_temp_files") if settings else CLEANUP_TEMP_FILES
    if not should_cleanup:
        return

    project_root = Path(__file__).resolve().parent
    outputs_dir = project_root / "outputs"
    temp_visuals_dir = outputs_dir / "temp_visuals"

    # 1. Delete all files in outputs/temp_visuals/ folder (keep the folder itself)
    if temp_visuals_dir.is_dir():
        for root, dirs, files in os.walk(temp_visuals_dir, topdown=False):
            for file_name in files:
                full_file_path = Path(root) / file_name
                try:
                    rel_path = full_file_path.relative_to(project_root).as_posix()
                except ValueError:
                    rel_path = full_file_path.as_posix()
                try:
                    full_file_path.unlink()
                    print(f"[CLEANUP] Deleted {rel_path}")
                except Exception as e:
                    print(f"[WARNING] Could not delete {rel_path}: {e}")
            for dir_name in dirs:
                full_dir_path = Path(root) / dir_name
                try:
                    full_dir_path.rmdir()
                except Exception:
                    pass

    # 2, 3 & 4. Delete temp music, intermediate audio files, non-short_*.mp4 files in outputs/
    if outputs_dir.is_dir():
        for item in outputs_dir.iterdir():
            if item.is_file():
                # IMPORTANT: Do NOT delete final short_*.mp4 files
                if item.name.startswith("short_") and item.name.endswith(".mp4"):
                    continue
                try:
                    rel_path = item.relative_to(project_root).as_posix()
                except ValueError:
                    rel_path = item.as_posix()
                try:
                    item.unlink()
                    print(f"[CLEANUP] Deleted {rel_path}")
                except Exception as e:
                    print(f"[WARNING] Could not delete {rel_path}: {e}")

    # 5. Clean up any orphan TEMP_MPY_*.mp3 files in the project root
    for item in project_root.iterdir():
        if item.is_file() and "TEMP_MPY_" in item.name and item.suffix.lower() == ".mp3":
            try:
                rel_path = item.name
                item.unlink()
                print(f"[CLEANUP] Deleted {rel_path}")
            except Exception as e:
                print(f"[WARNING] Could not delete {rel_path}: {e}")


def _print_video_summary(script, settings, video_path, video_info):
    metadata = get_script_metadata(script)
    width, height = video_info["width"], video_info["height"]
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    voice = f"IndicF5 reference: {Path(settings['indicf5_reference_audio']).name}"
    print("\n========== VIDEO SUMMARY ==========")
    print(f"Script:\n{spoken_text(script)}")
    print(
        "Character/Theme: "
        f"{_display_character(metadata['character'])} / {metadata['theme']}"
    )
    print(
        f"Duration: {video_info['duration']:.2f} sec "
        f"(target: {settings['duration_target']} sec)"
    )
    print(f"Aspect Ratio: {settings['aspect_ratio']}")
    print(f"Resolution: {width}x{height}")
    print(f"Voice used: {voice}")
    print("TTS provider: indicf5")
    print(f"File: {video_path}")
    print(f"File size: {file_size_mb:.2f} MB")
    print("===================================")


def _remove_artifacts(*paths):
    for path in paths:
        if path and os.path.exists(path):
            os.remove(path)


def _accept_video(script, video_path, enable_upload_override=False, settings=None):
    upload_enabled = enable_upload_override or ENABLE_UPLOAD
    if not upload_enabled:
        print(f"[SKIP] Upload disabled. Video saved at: {video_path}")
        return video_path

    narration_text = spoken_text(script)
    metadata_info = get_script_metadata(script)
    theme_val = metadata_info.get("theme") or (settings.get("theme") if settings else None)
    char_val = metadata_info.get("character") or (settings.get("character") if settings else None)

    from uploaders.factory import upload_to_platforms

    return upload_to_platforms(
        video_path,
        script=narration_text,
        theme=theme_val,
        character=char_val,
    )


def create_and_upload(
    auto_accept=False,
    cli_ratio=None,
    reset_ratio=False,
    character_override=None,
    duration_override=None,
    no_menu=False,
    enable_upload_override=False,
):
    if RANDOM_EFFECTS:
        effects = pick_random_effects()
    else:
        effects = {
            "ken_burns_pattern": "zoom_in",
            "transition": DEFAULT_TRANSITION,
            "color_filter": "none",
            "vignette": False,
            "caption_style": "bottom_center",
        }
    print(
        f"[INFO] Effects: ken_burns={effects['ken_burns_pattern']}, "
        f"transition={effects['transition']}, filter={effects['color_filter']}, "
        f"vignette={effects['vignette']}, caption={effects['caption_style']}"
    )

    settings = _default_settings()
    settings["effects"] = effects

    # Load from config_state.json if available (aspect_ratio, duration, music_volume, tts_rate, tts_pitch)
    saved_state = load_config_state()
    if saved_state:
        print("[INFO] Loaded settings from config_state.json")
        if "aspect_ratio" in saved_state:
            settings["aspect_ratio"] = str(saved_state["aspect_ratio"])
            print(f"[INFO] Aspect Ratio: {settings['aspect_ratio']} (from saved state)")
        if "duration" in saved_state:
            settings["duration_target"] = int(saved_state["duration"])
            settings["duration"] = int(saved_state["duration"])
            print(f"[INFO] Duration: {settings['duration_target']} sec (from saved state)")
        if "music_volume" in saved_state:
            try:
                vol = float(saved_state["music_volume"])
                settings["music_volume"] = vol
                print(f"[INFO] Background Music Volume: {int(round(vol * 100))}% (from saved state)")
            except (ValueError, TypeError):
                pass
        if "tts_rate" in saved_state:
            settings["tts_rate"] = str(saved_state["tts_rate"])
            print(f"[INFO] TTS Rate: {settings['tts_rate']} (from saved state)")
        if "tts_pitch" in saved_state:
            settings["tts_pitch"] = str(saved_state["tts_pitch"])
            print(f"[INFO] TTS Pitch: {settings['tts_pitch']} (from saved state)")
        if "caption_style" in saved_state:
            settings["caption_style"] = str(saved_state["caption_style"])
            print(f"[INFO] Caption Style: {settings['caption_style']} (from saved state)")
        if "brightness" in saved_state:
            try:
                b_val = int(saved_state["brightness"])
                settings["brightness"] = b_val
                print(f"[INFO] Brightness: {b_val}% (from saved state)")
            except (ValueError, TypeError):
                pass
        if "contrast" in saved_state:
            try:
                c_val = int(saved_state["contrast"])
                settings["contrast"] = c_val
                print(f"[INFO] Contrast: {c_val}% (from saved state)")
            except (ValueError, TypeError):
                pass

    # Force TTS provider to indicf5
    settings["tts_provider"] = "indicf5"

    # Reset ratio if flag provided
    if reset_ratio:
        settings["aspect_ratio"] = ASPECT_RATIO or "9:16"
        print(f"[INFO] Aspect ratio reset to .env default: {settings['aspect_ratio']}")

    # Apply CLI flag overrides (taking priority)
    if cli_ratio:
        settings["aspect_ratio"] = cli_ratio.strip()
        print(f"[INFO] Aspect Ratio CLI override: {settings['aspect_ratio']}")
    if duration_override is not None:
        settings["duration_target"] = int(duration_override)
        settings["duration"] = int(duration_override)
        print(f"[INFO] Duration CLI override: {settings['duration_target']} sec")

    # Show menu unless --no-menu flag is passed (FIX 1)
    if no_menu:
        save_config_state(settings)
    else:
        settings = show_settings_menu(settings)

    effects["brightness"] = settings.get("brightness", 0)
    effects["contrast"] = settings.get("contrast", 0)
    settings["effects"] = effects

    settings = _merge_settings(settings)


    # Always pick a dynamic theme on every run
    theme_config = _select_dynamic_job(
        settings,
        character_override=character_override,
        duration_override=settings["duration_target"],
    )
    if not theme_config:
        raise RuntimeError("Failed to select theme_config.")

    selected_voice = _determine_voice_for_theme(theme_config)
    settings["tts_voice"] = selected_voice

    script = _generate_script(settings)

    while True:
        print(f"\nGenerating video... {datetime.now()}")
        audio_path, boundaries_path, video_path, video_info = _render_video(script, settings)
        if auto_accept:
            return _accept_video(script, video_path, enable_upload_override=enable_upload_override, settings=settings)

        _print_video_summary(script, settings, video_path, video_info)
        while True:
            choice = input(f"{APPROVAL_PROMPT}\n> ").strip().lower()
            if choice == "y":
                return _accept_video(script, video_path, enable_upload_override=enable_upload_override, settings=settings)
            if choice == "u":
                print("[UPLOAD] User chose [u] Upload Now")
                try:
                    return _accept_video(script, video_path, enable_upload_override=True, settings=settings)
                except Exception as upload_err:
                    print(f"[ERROR] Upload failed: {upload_err}. Video preserved at: {video_path}")
                    return video_path
            if choice == "q":
                print(f"[QUIT] Approval stopped. Video remains at: {video_path}")
                return None
            if choice == "n":
                _remove_artifacts(audio_path, boundaries_path, video_path)
                theme_config = _select_dynamic_job(
                    settings,
                    character_override=character_override,
                    duration_override=settings["duration_target"],
                )
                if not theme_config:
                    raise RuntimeError("Failed to select theme_config on regeneration.")
                selected_voice = _determine_voice_for_theme(theme_config)
                settings["tts_voice"] = selected_voice
                script = _generate_script(settings)
                break
            print("Please enter y, u, n, or q.")



def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate and review a Kids Short")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Skip the menu and approval prompt, auto-accept generated video",
    )
    parser.add_argument(
        "--no-menu",
        action="store_true",
        help="Skip the pre-run settings menu, use saved settings / defaults",
    )
    parser.add_argument(
        "--ratio",
        type=str,
        default=None,
        help="Set aspect ratio (e.g., 9:16, 12:16, 14:16, 1:1, 4:5)",
    )
    parser.add_argument(
        "--reset-ratio",
        action="store_true",
        help="Reset saved aspect ratio state to .env default",
    )
    parser.add_argument(
        "--character",
        type=str,
        default=None,
        help="Force a specific character theme (e.g., Hanuman, Krishna)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Force video duration in seconds (15-180)",
    )

    parser.add_argument(
        "--upload",
        action="store_true",
        help="Enable YouTube upload for this run (overrides ENABLE_UPLOAD)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=1,
        help="Run the pipeline N times in batch mode",
    )
    args = parser.parse_args(argv)

    batch_count = max(1, args.batch)
    results = []
    for run_idx in range(batch_count):
        if batch_count > 1:
            print(f"\n==========================================")
            print(f"   BATCH RUN {run_idx + 1} OF {batch_count}")
            print(f"==========================================")
        res = create_and_upload(
            auto_accept=args.auto,
            cli_ratio=args.ratio,
            reset_ratio=args.reset_ratio,
            character_override=args.character,
            duration_override=args.duration,
            no_menu=args.no_menu,
            enable_upload_override=args.upload,
        )
        results.append(res)
    return results[0] if len(results) == 1 else results


if __name__ == "__main__":
    main()
