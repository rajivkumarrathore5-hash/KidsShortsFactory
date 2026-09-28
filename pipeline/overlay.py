import json
import os
import random
import shutil
import subprocess
from pathlib import Path

OVERLAYS_DIR = Path(__file__).resolve().parent.parent / "assets" / "overlays"


def ask_overlay_settings(settings: dict) -> dict:
    """
    Prompts user for overlay settings in pre-run menu.
    """
    print("\n==========================================")
    print("         🎨 OVERLAY SETTINGS              ")
    print("==========================================")
    current_enabled = settings.get("overlay_enabled", True)
    current_trans = int(settings.get("overlay_transparency", 50))

    prompt_default = "Y/n" if current_enabled else "y/N"
    val = input(f"Use overlays? [{prompt_default}]: ").strip().lower()
    if val == "":
        enabled = current_enabled
    elif val in ("y", "yes", "1", "true"):
        enabled = True
    elif val in ("n", "no", "0", "false"):
        enabled = False
    else:
        print("[WARNING] Invalid choice, keeping current setting.")
        enabled = current_enabled

    settings["overlay_enabled"] = enabled
    if enabled:
        print("Recommended range: 30% - 60% (devotional ke liye best)")
        trans_input = input(f"Enter transparency % (10-100) [current: {current_trans}%]: ").strip()
        if trans_input == "":
            transparency = current_trans
        else:
            try:
                t_val = int(trans_input)
                if 10 <= t_val <= 100:
                    transparency = t_val
                else:
                    print(f"[ERROR] Transparency must be between 10 and 100. Keeping {current_trans}%.")
                    transparency = current_trans
            except ValueError:
                print(f"[ERROR] Invalid number. Keeping {current_trans}%.")
                transparency = current_trans
        settings["overlay_transparency"] = transparency
        print(f"[OK] Overlays enabled with {transparency}% transparency.")
    else:
        print("[OK] Overlays disabled.")

    return settings


def get_video_duration(video_path: str) -> float:
    """
    Retrieves video duration in seconds using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        dur_str = res.stdout.strip()
        return float(dur_str)
    except Exception as e:
        print(f"[WARNING] ffprobe failed to get duration for {video_path}: {e}")
        return 0.0


def get_video_resolution(video_path: str) -> tuple[int, int]:
    """
    Retrieves video resolution (width, height) using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        str(video_path),
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(res.stdout)
        stream = data.get("streams", [{}])[0]
        return int(stream.get("width", 1080)), int(stream.get("height", 1920))
    except Exception as e:
        print(f"[WARNING] ffprobe failed to get resolution for {video_path}: {e}")
        return 1080, 1920


def get_random_overlays(count: int = 2) -> list[str]:
    """
    Picks count random overlay video paths from assets/overlays folder.
    """
    if not OVERLAYS_DIR.is_dir():
        print(f"[OVERLAY] Warning: Overlays directory not found at {OVERLAYS_DIR}")
        return []

    valid_extensions = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    candidates = [
        str(f) for f in OVERLAYS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in valid_extensions
    ]

    if not candidates:
        print("[OVERLAY] Warning: No overlay videos found in assets/overlays.")
        return []

    pick_count = min(count, len(candidates))
    return random.sample(candidates, pick_count)


def apply_overlays(input_video: str, output_video: str, config: dict = None) -> str:
    """
    Applies 2-3 looped, zoom-to-fit screen blended overlays with specified transparency.
    """
    if config is None:
        config = {}

    enabled = config.get("overlay_enabled", True)
    if not enabled:
        if input_video != output_video:
            shutil.copy2(input_video, output_video)
        return output_video

    transparency = int(config.get("overlay_transparency", 50))
    alpha = max(0.10, min(1.00, transparency / 100.0))

    # Pick 2-3 overlays
    overlay_count = random.randint(2, 3)
    overlays = get_random_overlays(overlay_count)
    if not overlays:
        print("[OVERLAY] Gracefully skipping overlays (none found).")
        if input_video != output_video:
            shutil.copy2(input_video, output_video)
        return output_video

    width, height = get_video_resolution(input_video)
    duration = get_video_duration(input_video)
    if duration <= 0:
        duration = float(config.get("duration_target", 30))

    overlay_names = ", ".join(Path(p).name for p in overlays)
    print(f"[OVERLAY] Applying {len(overlays)} overlays ({overlay_names}) with {transparency}% opacity (screen blend)...")

    # Build FFmpeg command
    cmd = ["ffmpeg", "-y", "-i", str(input_video)]
    for ov_path in overlays:
        cmd.extend(["-stream_loop", "-1", "-i", str(ov_path)])

    filter_complex_parts = []
    # Base video RGBA
    filter_complex_parts.append("[0:v]format=rgba[b0]")

    # Overlay preps
    for idx, _ in enumerate(overlays, start=1):
        filter_complex_parts.append(
            f"[{idx}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,format=rgba,colorchannelmixer=aa={alpha:.2f}[ov{idx}]"
        )

    # Blend chain
    for idx in range(1, len(overlays) + 1):
        prev_layer = f"b{idx-1}"
        curr_layer = f"b{idx}"
        filter_complex_parts.append(
            f"[{prev_layer}][ov{idx}]blend=all_mode=screen:all_opacity={alpha:.2f}[{curr_layer}]"
        )

    last_layer = f"b{len(overlays)}"
    filter_complex_parts.append(f"[{last_layer}]format=yuv420p[outv]")

    filter_complex_str = ";\n".join(filter_complex_parts)

    import tempfile
    temp_script = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        temp_script.write(filter_complex_str)
        temp_script.close()

        cmd.extend([
            "-filter_complex_script", temp_script.name,
            "-map", "[outv]",
            "-map", "0:a?",
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "copy",
            str(output_video),
        ])

        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"[OVERLAY] Successfully applied overlays -> {output_video}")
        return output_video
    except Exception as e:
        err_msg = str(e)
        if isinstance(e, subprocess.CalledProcessError) and e.stderr:
            err_msg = e.stderr.decode("utf-8", errors="replace")
        print(f"[WARNING] Overlay application failed: {err_msg}. Falling back to base video.")
        if input_video != output_video and os.path.isfile(input_video):
            shutil.copy2(input_video, output_video)
        return output_video
    finally:
        try:
            if os.path.exists(temp_script.name):
                os.remove(temp_script.name)
        except Exception:
            pass
