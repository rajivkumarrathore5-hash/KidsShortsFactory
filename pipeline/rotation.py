import json
from pathlib import Path
from pipeline.pre_run_settings import load_config_state, CONFIG_STATE_PATH

SHORT_DURATION_PRESETS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
STORY_DURATION_PRESETS = [60, 75, 90, 105, 120, 135, 150, 165, 180]


def resolve_video_mode(selected_mode: str, config_state: dict = None) -> str:
    """
    Resolves the active video mode. If selected_mode is 'auto',
    alternates between 'short' and 'story' based on last_video_mode.
    """
    state = load_config_state() if config_state is None else {**load_config_state(), **config_state}
    mode_str = str(selected_mode or "auto").strip().lower()

    if mode_str == "auto":
        last_mode = str(state.get("last_video_mode") or "").strip().lower()
        if last_mode == "short":
            next_mode = "story"
        elif last_mode == "story":
            next_mode = "short"
        else:
            next_mode = "short"

        print(f"[MODE] Auto rotation enabled: last={last_mode or 'none'} -> next={next_mode}")
        _persist_config_state({"last_video_mode": next_mode})
        return next_mode
    else:
        chosen_mode = "story" if mode_str == "story" else "short"
        _persist_config_state({"last_video_mode": chosen_mode})
        return chosen_mode


def resolve_duration(selected_duration, current_mode: str, config_state: dict = None) -> int:
    """
    Resolves the video duration in seconds. If selected_duration is 'auto',
    rotates through preset durations based on the active mode (short / story).
    """
    state = load_config_state() if config_state is None else {**load_config_state(), **config_state}
    is_auto = False
    if selected_duration is None or str(selected_duration).strip().lower() == "auto":
        is_auto = True
    elif isinstance(selected_duration, str) and not selected_duration.isdigit():
        is_auto = True

    presets = SHORT_DURATION_PRESETS if current_mode == "short" else STORY_DURATION_PRESETS

    if is_auto:
        raw_last = state.get("last_duration")
        last_dur = None
        if raw_last is not None:
            try:
                last_dur = int(raw_last)
            except (ValueError, TypeError):
                last_dur = None

        if last_dur is not None and last_dur in presets:
            idx = presets.index(last_dur)
            next_dur = presets[(idx + 1) % len(presets)]
        else:
            next_dur = presets[0]

        print(f"[DURATION] Auto rotation enabled: last={last_dur if last_dur is not None else 'none'} -> next={next_dur}")
        _persist_config_state({"last_duration": next_dur})
        return next_dur
    else:
        try:
            dur = int(selected_duration)
        except (ValueError, TypeError):
            dur = presets[0]

        _persist_config_state({"last_duration": dur})
        return dur


def _persist_config_state(updates: dict):
    try:
        current_disk_state = load_config_state()
        merged = {**current_disk_state, **updates}
        CONFIG_STATE_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARNING] Could not save rotation state to config_state.json: {e}")
