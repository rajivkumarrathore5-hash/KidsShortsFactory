import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from PIL import Image, ImageColor, ImageDraw, ImageFont
import requests
from text_unidecode import unidecode


NOTO_FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/"
    "notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"
)
MAX_CAPTION_WORDS = 4


def _get_audio_duration(audio_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ValueError(f"Invalid audio duration: {duration}")
    return duration


get_audio_duration = _get_audio_duration


def allocate_scene_durations(scenes, total_audio_duration, min_duration=3.0, max_duration=5.0):
    scene_count = len(scenes)
    if scene_count == 0:
        raise ValueError("A video requires at least one scene.")
    if total_audio_duration <= 0:
        raise ValueError("Audio duration must be positive.")

    weights = [max(1, len(scene.get("text", "").strip())) for scene in scenes]
    lower = float(min_duration)
    upper = float(max_duration)
    if total_audio_duration < scene_count * lower or total_audio_duration > scene_count * upper:
        lower = upper = total_audio_duration / scene_count

    durations = [None] * scene_count
    remaining = set(range(scene_count))
    remaining_duration = float(total_audio_duration)
    while remaining:
        total_weight = sum(weights[index] for index in remaining)
        proposed = {
            index: remaining_duration * weights[index] / total_weight
            for index in remaining
        }
        constrained = [
            (index, lower if value < lower else upper)
            for index, value in proposed.items()
            if value < lower or value > upper
        ]
        if not constrained:
            for index, value in proposed.items():
                durations[index] = value
            break
        for index, value in constrained:
            durations[index] = value
            remaining_duration -= value
            remaining.remove(index)

    correction = total_audio_duration - sum(durations)
    durations[-1] += correction
    return durations


def resolution_for_aspect_ratio(aspect_ratio):
    match = re.fullmatch(r"(\d+):(\d+)", aspect_ratio.strip())
    if not match:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}")
    ratio_width, ratio_height = map(int, match.groups())
    if ratio_width == 0 or ratio_height == 0:
        raise ValueError(f"Aspect ratio values must be positive: {aspect_ratio}")
    if ratio_width <= ratio_height:
        width = 1080
        height = round(1080 * ratio_height / ratio_width)
    else:
        height = 1080
        width = round(1080 * ratio_width / ratio_height)
    width = max(2, width + (width % 2))
    height = max(2, height + (height % 2))
    return width, height


def get_video_info(video_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    probe = json.loads(result.stdout)
    streams = probe.get("streams", [])
    if not streams or "duration" not in probe.get("format", {}):
        raise ValueError(f"Could not read video metadata: {video_path}")
    return {
        "duration": float(probe["format"]["duration"]),
        "width": int(streams[0]["width"]),
        "height": int(streams[0]["height"]),
    }


def _split_caption_lines(text, max_words=MAX_CAPTION_WORDS):
    words = text.split()
    return [
        " ".join(words[index:index + max_words])
        for index in range(0, len(words), max_words)
    ]


def build_caption_segments(text, duration, word_boundaries=None, mode="line_by_line"):
    if mode == "full":
        return [{"text": text.strip(), "start": 0.0, "end": duration}]
    if mode != "line_by_line":
        raise ValueError(f"Unsupported caption mode: {mode}")

    boundaries = [
        {
            "text": item["text"].strip(),
            "start": max(0.0, float(item["start"])),
            "end": min(duration, float(item["end"])),
        }
        for item in (word_boundaries or [])
        if item.get("text", "").strip() and float(item.get("start", duration)) < duration
    ]
    if boundaries:
        groups = [
            boundaries[index:index + MAX_CAPTION_WORDS]
            for index in range(0, len(boundaries), MAX_CAPTION_WORDS)
        ]
        segments = []
        for index, group in enumerate(groups):
            start = group[0]["start"]
            end = group[-1]["end"]
            if index + 1 < len(groups):
                end = max(end, groups[index + 1][0]["start"])
            end = min(duration, end)
            if end > start:
                segments.append(
                    {"text": " ".join(word["text"] for word in group), "start": start, "end": end}
                )
        if segments:
            return segments

    lines = _split_caption_lines(text)
    total_characters = sum(max(1, len(line)) for line in lines)
    current_time = 0.0
    segments = []
    for index, line in enumerate(lines):
        if index == len(lines) - 1:
            end_time = duration
        else:
            end_time = current_time + duration * max(1, len(line)) / total_characters
        segments.append({"text": line, "start": current_time, "end": end_time})
        current_time = end_time
    return segments


def _load_caption_font(font_path, font_size):
    font_file = Path(font_path)
    if not font_file.is_absolute():
        font_file = Path(__file__).resolve().parents[1] / font_file

    if not font_file.is_file():
        print(f"[ERROR] Devanagari font not found: {font_file}")
        print("[INFO] Attempting to download Noto Sans Devanagari.")
        try:
            response = requests.get(NOTO_FONT_URL, timeout=30)
            response.raise_for_status()
            font_file.parent.mkdir(parents=True, exist_ok=True)
            font_file.write_bytes(response.content)
        except (OSError, requests.RequestException) as error:
            print(f"[ERROR] Noto Sans Devanagari download failed: {error}")
            print("[WARNING] Captions will use English transliteration.")
            try:
                fallback_font = ImageFont.truetype("arial.ttf", font_size)
                return str(Path(fallback_font.path).resolve()), True
            except OSError:
                return "", True

    ImageFont.truetype(str(font_file), font_size)
    print(f"[OK] Devanagari font loaded: {font_file}")
    return str(font_file), False


def _escape_filter_path(path):
    return (
        str(Path(path).resolve())
        .replace("\\", "/")
        .replace(":", r"\:")
        .replace("'", r"\'")
    )


def _create_gradient(path, width, height):
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    top_color = (20, 62, 77)
    bottom_color = (150, 57, 100)
    for y in range(height):
        progress = y / max(1, height - 1)
        color = tuple(
            round(top_color[channel] * (1 - progress) + bottom_color[channel] * progress)
            for channel in range(3)
        )
        draw.line((0, y, width, y), fill=color)
    image.save(path)


def _create_title_card(path, width, height, text, font_path, font_size):
    _create_gradient(path, width, height)
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        font = ImageFont.load_default()
    draw.text(
        (width // 2, height // 2),
        text,
        font=font,
        fill="white",
        anchor="mm",
        stroke_width=3,
        stroke_fill="black",
    )
    image.save(path)


def render_video(
    audio_path,
    text,
    output_path,
    visual_url=None,
    duration=18,
    aspect_ratio="9:16",
    image_paths=None,
    word_boundaries=None,
    caption_mode="line_by_line",
    font_path="assets/fonts/NotoSansDevanagari-Regular.ttf",
    caption_font_size=48,
    caption_color="white",
    caption_border_width=2,
    caption_border_color="black",
    scenes=None,
    scene_durations=None,
    ken_burns_enabled=True,
    ken_burns_zoom=1.05,
    scene_transition="fade",
    scene_transition_duration=0.4,
    background_music=True,
    music_path="assets/music/kids_bg.mp3",
    music_prompt=None,
    music_volume=0.15,
    intro_enabled=False,
    outro_enabled=False,
    channel_name="Kids Shorts Factory",
    effects=None,
    caption_style=None,
):
    temporary_directory = None
    try:
        effects = effects or {}
        kb_pattern = effects.get("ken_burns_pattern", "zoom_in")
        raw_transition = effects.get("transition", scene_transition or "fade")
        TRANSITION_MAP = {
            "fade": "fade",
            "slide_left": "slideleft",
            "slide_right": "slideright",
            "zoom_in": "zoomin",
            "wipe": "wipeleft",
            "circle": "circlecrop",
        }
        scene_transition = TRANSITION_MAP.get(raw_transition, raw_transition)
        color_filter_opt = effects.get("color_filter", "none")
        vignette_opt = effects.get("vignette", False)
        caption_style_opt = (
            caption_style
            or effects.get("caption_style")
            or "bottom_bold"
        )

        audio_duration = _get_audio_duration(audio_path)
        width, height = resolution_for_aspect_ratio(aspect_ratio)
        temporary_directory = tempfile.TemporaryDirectory(prefix="kids_short_render_")
        temp_path = Path(temporary_directory.name)
        scene_data = list(scenes or [])
        paths = list(image_paths or [])
        scene_count = max(len(scene_data), len(paths), 1)
        if not scene_data:
            scene_data = [{"text": text, "visual_keywords": []} for _ in range(scene_count)]
        if not scene_durations or len(scene_durations) != scene_count:
            scene_durations = allocate_scene_durations(
                scene_data, audio_duration, min_duration=3, max_duration=5
            )
        else:
            scene_durations = [float(value) for value in scene_durations]
            if any(value <= 0 for value in scene_durations):
                raise ValueError("Every scene duration must be positive.")
            duration_scale = audio_duration / sum(scene_durations)
            scene_durations = [value * duration_scale for value in scene_durations]

        scene_paths = []
        for index in range(scene_count):
            image_path = paths[index] if index < len(paths) else None
            try:
                if not image_path:
                    raise OSError("No image was returned for this scene")
                with Image.open(image_path) as image:
                    image.verify()
                scene_paths.append(str(image_path))
            except (OSError, ValueError) as error:
                print(f"[WARNING] Scene {index + 1} visual unavailable; using its gradient: {error}")
                gradient_path = temp_path / f"scene_{index + 1}_fallback.jpg"
                _create_gradient(gradient_path, width, height)
                scene_paths.append(str(gradient_path))

        clip_paths = []
        clip_durations = []
        intro_duration = 1.0 if intro_enabled else 0.0
        outro_duration = 1.0 if outro_enabled else 0.0
        if intro_enabled:
            intro_path = temp_path / "intro.jpg"
            _create_title_card(intro_path, width, height, channel_name, font_path, caption_font_size)
            clip_paths.append(str(intro_path))
            clip_durations.append(intro_duration)
        clip_paths.extend(scene_paths)
        clip_durations.extend(scene_durations)
        if outro_enabled:
            outro_path = temp_path / "outro.jpg"
            _create_title_card(outro_path, width, height, "Subscribe", font_path, caption_font_size)
            clip_paths.append(str(outro_path))
            clip_durations.append(outro_duration)

        use_transition = (
            scene_transition != "none"
            and scene_transition_duration > 0
            and len(clip_paths) > 1
        )
        transition_duration = min(
            float(scene_transition_duration),
            min(clip_durations) / 2,
        ) if use_transition else 0.0
        render_clip_durations = list(clip_durations)
        final_video_duration = sum(clip_durations)

        segments = build_caption_segments(
            text, audio_duration, word_boundaries=word_boundaries, mode=caption_mode
        )
        print(f"[OK] Generated {len(segments)} caption segment(s) ({caption_mode}).")
        selected_font_path, transliterate = _load_caption_font(font_path, caption_font_size)
        if transliterate:
            print("[WARNING] Devanagari captions transliterated to English.")

        caption_paths = []
        for index, segment in enumerate(segments):
            caption_path = temp_path / f"caption_{index:03d}.txt"
            caption_text = unidecode(segment["text"]) if transliterate else segment["text"]
            caption_path.write_text(caption_text, encoding="utf-8")
            caption_paths.append(str(caption_path))

        rendered_clips = []
        for index, (scene_path, clip_duration) in enumerate(zip(clip_paths, render_clip_durations)):
            clip_path = temp_path / f"scene_clip_{index:02d}.mp4"
            scale_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2,setsar=1"
            )
            if ken_burns_enabled:
                zoom_frames = max(1, round(clip_duration * 30))
                effective_zoom = min(1.05, max(1.0, float(ken_burns_zoom)))
                extra_rot = ""
                if kb_pattern == "zoom_out":
                    zoom_expr = f"max(1.0,{effective_zoom:.4f}-({effective_zoom - 1.0:.4f})*on/{zoom_frames})"
                    x_expr = "(iw-iw/zoom)*0.5"
                    y_expr = "(ih-ih/zoom)*0.5"
                elif kb_pattern == "pan_left":
                    zoom_expr = f"{effective_zoom:.4f}"
                    x_expr = f"(iw-iw/zoom)*(1.0-on/{zoom_frames})"
                    y_expr = "(ih-ih/zoom)*0.5"
                elif kb_pattern == "pan_right":
                    zoom_expr = f"{effective_zoom:.4f}"
                    x_expr = f"(iw-iw/zoom)*(on/{zoom_frames})"
                    y_expr = "(ih-ih/zoom)*0.5"
                elif kb_pattern == "diagonal":
                    zoom_expr = f"min(1.0+({effective_zoom - 1.0:.4f})*on/{zoom_frames},{effective_zoom:.4f})"
                    x_expr = f"(iw-iw/zoom)*(on/{zoom_frames})"
                    y_expr = f"(ih-ih/zoom)*(on/{zoom_frames})"
                elif kb_pattern == "rotate_slow":
                    zoom_expr = "1.04"
                    x_expr = "(iw-iw/zoom)*0.5"
                    y_expr = "(ih-ih/zoom)*0.5"
                    extra_rot = ",rotate=a='(0.3*PI/180)*t':c=black:ow=iw:oh=ih"
                else:  # zoom_in or default
                    zoom_expr = f"min(1.0+({effective_zoom - 1.0:.4f})*on/{zoom_frames},{effective_zoom:.4f})"
                    x_expr = "(iw-iw/zoom)*0.5"
                    y_expr = "(ih-ih/zoom)*0.5"

                scale_filter += (
                    f",zoompan=z='{zoom_expr}':x='{x_expr}':"
                    f"y='{y_expr}':d=1:s={width}x{height}:fps=30"
                    f",scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
                    f"{extra_rot}"
                )
            scale_filter += f",fps=30,trim=duration={clip_duration:.6f},setpts=PTS-STARTPTS,format=yuv420p"

            clip_command = [
                "ffmpeg", "-y", "-f", "image2", "-loop", "1", "-framerate", "30",
                "-i", scene_path, "-vf", scale_filter,
                "-t", f"{clip_duration:.6f}", "-an", "-c:v", "libx264",
                "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30",
                "-video_track_timescale", "30000", str(clip_path),
            ]
            clip_result = subprocess.run(clip_command, capture_output=True, text=True)
            if clip_result.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg failed to render scene {index + 1}: {clip_result.stderr}"
                )
            rendered_clips.append(str(clip_path))

        cmd = ["ffmpeg", "-y"]
        for clip_path in rendered_clips:
            cmd.extend(["-i", clip_path])
        audio_index = len(clip_paths)
        cmd.extend(["-i", audio_path])

        # Background music selection & handling (Short Mode vs Story Mode)
        selected_music_file = None
        use_music = False
        music_offset = 0.0
        story_mode_music = False
        section_music_inputs = []

        if background_music:
            project_root = Path(__file__).resolve().parents[1]
            search_dirs = [
                project_root / "assets" / "music",
                project_root / "data" / "music",
                Path("assets/music"),
                Path("data/music"),
            ]
            music_files_dict = {}
            for search_dir in search_dirs:
                if search_dir.is_dir():
                    for mp3 in search_dir.glob("*.mp3"):
                        if mp3.is_file() and mp3.name not in music_files_dict:
                            music_files_dict[mp3.name] = mp3

            available_files = list(music_files_dict.values())
            has_sections = any(isinstance(s, dict) and s.get("section") for s in scene_data)

            if has_sections and available_files:
                story_mode_music = True
                use_music = True
                print("[MUSIC] Story Mode section music enabled (crossfade across sections)")

                SECTION_MUSIC_CANDIDATES = {
                    "hook": ["dhol_energy.mp3", "tabla_bhakti.mp3"],
                    "setup": ["flute_soft.mp3", "sitar_calm.mp3"],
                    "story": ["sitar_calm.mp3", "tabla_bhakti.mp3"],
                    "twist": ["dhol_energy.mp3", "tabla_bhakti1.mp3"],
                    "moral": ["flute_soft.mp3", "sitar_calm.mp3"],
                    "cta": ["flute_soft.mp3"],
                }

                current_time = intro_duration
                next_input_idx = audio_index + 1

                for sc_idx, sc_dur in enumerate(scene_durations[:len(scene_data)]):
                    sec_tag = str(scene_data[sc_idx].get("section", "story")).lower()
                    candidates = SECTION_MUSIC_CANDIDATES.get(sec_tag, ["flute_soft.mp3"])
                    chosen_mp3 = None
                    for cand in candidates:
                        if cand in music_files_dict:
                            chosen_mp3 = music_files_dict[cand]
                            break
                    if not chosen_mp3:
                        chosen_mp3 = random.choice(available_files)

                    try:
                        mp3_dur = _get_audio_duration(str(chosen_mp3))
                        max_off = max(0.0, mp3_dur - sc_dur - 2.0)
                        off_val = round(random.uniform(0, max_off), 2) if max_off > 0 else 0.0
                    except Exception:
                        off_val = 0.0

                    section_music_inputs.append(
                        {
                            "input_idx": next_input_idx,
                            "file_path": chosen_mp3,
                            "offset": off_val,
                            "start_time": current_time,
                            "duration": sc_dur,
                            "section": sec_tag,
                        }
                    )
                    cmd.extend(["-ss", f"{off_val}", "-stream_loop", "-1", "-i", str(chosen_mp3)])
                    next_input_idx += 1
                    current_time += sc_dur

            elif available_files:
                selected_music_file = random.choice(available_files)
                use_music = True
                print(f"[MUSIC] Randomly selected: {selected_music_file.name}")
            elif music_path:
                fallback_path = Path(music_path)
                if not fallback_path.is_absolute():
                    fallback_path = project_root / fallback_path
                if fallback_path.is_file():
                    selected_music_file = fallback_path
                    use_music = True
                    print(f"[MUSIC] Randomly selected: {selected_music_file.name}")

            if use_music and not story_mode_music and selected_music_file:
                try:
                    dur_val = _get_audio_duration(str(selected_music_file))
                    max_offset = dur_val - final_video_duration - 5.0
                    if max_offset > 0:
                        music_offset = round(random.uniform(0, max_offset), 2)
                    else:
                        music_offset = 0.0
                    print(f"[MUSIC] Playing from offset: {music_offset}s (file duration: {dur_val}s)")
                except Exception as offset_err:
                    music_offset = 0.0
                    print(f"[WARNING] Music offset calculation failed ({offset_err}), defaulting to 0s")

        music_index = None
        if use_music and not story_mode_music and selected_music_file:
            music_index = audio_index + 1
            if music_offset > 0:
                cmd.extend(["-ss", f"{music_offset}", "-stream_loop", "-1", "-i", str(selected_music_file)])
            else:
                cmd.extend(["-stream_loop", "-1", "-i", str(selected_music_file)])

        filters = []
        if len(rendered_clips) == 1:
            filters.append("[0:v]null[background]")
        elif use_transition:
            current_label = "0:v"
            elapsed = 0.0
            for index in range(1, len(rendered_clips)):
                elapsed += clip_durations[index - 1]
                next_label = f"xfade{index}"
                offset = elapsed - transition_duration * index
                filters.append(
                    f"[{current_label}][{index}:v]xfade="
                    f"transition={scene_transition}:duration={transition_duration:.6f}:"
                    f"offset={offset:.6f}[{next_label}]"
                )
                current_label = next_label
            total_overlap = transition_duration * (len(rendered_clips) - 1)
            filters.append(
                f"[{current_label}]tpad=stop_mode=clone:stop_duration={total_overlap:.6f},"
                f"trim=duration={final_video_duration:.6f}[background]"
            )
        else:
            scene_labels = "".join(f"[{index}:v]" for index in range(len(rendered_clips)))
            filters.append(f"{scene_labels}concat=n={len(rendered_clips)}:v=1:a=0[background]")

        current_label = "background"
        b_pct = int(effects.get("brightness", 0)) if effects else 0
        c_pct = int(effects.get("contrast", 0)) if effects else 0
        print(f"[INFO] Brightness: {b_pct}% | Contrast: {c_pct}%")

        if b_pct != 0 or c_pct != 0:
            b_val = b_pct / 100.0
            c_val = 1.0 + (c_pct / 100.0)
            filters.append(f"[{current_label}]eq=brightness={b_val:.2f}:contrast={c_val:.2f}[eq_adjusted]")
            current_label = "eq_adjusted"

        COLOR_FILTER_MAP = {
            "none": "",
            "warm": "colorbalance=rs=0.1:gs=0.05:bs=-0.05",
            "cool": "colorbalance=rs=-0.05:gs=0.0:bs=0.1",
            "vintage": "eq=saturation=0.85:contrast=1.1,colorbalance=rs=0.1:bs=-0.08",
            "high_contrast": "eq=contrast=1.25:saturation=1.1",
            "cinematic": "eq=contrast=1.15:saturation=0.9,colorbalance=rs=0.05:bs=0.05",
        }
        color_filter_str = COLOR_FILTER_MAP.get(color_filter_opt, "")
        if color_filter_str:
            filters.append(f"[{current_label}]{color_filter_str}[filtered]")
            current_label = "filtered"
        if vignette_opt:
            filters.append(f"[{current_label}]vignette=PI/4[vignetted]")
            current_label = "vignetted"


        for index, (segment, _) in enumerate(zip(segments, caption_paths)):
            next_label = f"captioned{index}"
            start_time = max(0.0, segment["start"]) + intro_duration
            end_time = min(audio_duration, segment["end"]) + intro_duration

            fontfile_option = (
                f":fontfile='{_escape_filter_path(selected_font_path)}'"
                if selected_font_path
                else ""
            )

            # Position: Bottom Center, inside safe area (150px from bottom)
            draw_y_expr = "h-text_h-150"

            if caption_style_opt == "glitch":
                # Glitch chromatic offset (cyan, magenta, white)
                lbl_c = f"glitch_c_{index}"
                lbl_m = f"glitch_m_{index}"
                filters.append(
                    f"[{current_label}]drawtext=textfile='{_escape_filter_path(caption_paths[index])}'"
                    f"{fontfile_option}:fontcolor=0x00FFFF:fontsize={caption_font_size+4}"
                    f":x=(w-text_w)/2-3:y=h-text_h-148:text_shaping=1"
                    f":enable='between(t,{start_time:.3f},{end_time:.3f})'[{lbl_c}]"
                )
                filters.append(
                    f"[{lbl_c}]drawtext=textfile='{_escape_filter_path(caption_paths[index])}'"
                    f"{fontfile_option}:fontcolor=0xFF00FF:fontsize={caption_font_size+4}"
                    f":x=(w-text_w)/2+3:y=h-text_h-152:text_shaping=1"
                    f":enable='between(t,{start_time:.3f},{end_time:.3f})'[{lbl_m}]"
                )
                filters.append(
                    f"[{lbl_m}]drawtext=textfile='{_escape_filter_path(caption_paths[index])}'"
                    f"{fontfile_option}:fontcolor=0xFFFFFF:fontsize={caption_font_size+4}"
                    f":borderw=2:bordercolor=0x000000:x=(w-text_w)/2:y=h-text_h-150:text_shaping=1"
                    f":enable='between(t,{start_time:.3f},{end_time:.3f})'[{next_label}]"
                )
            else:
                draw_font_size = caption_font_size
                font_color_hex = "0xFFFFFF"
                border_color_hex = "0x000000"
                draw_border_w = 2
                box_option = ":box=1:boxcolor=black@0.5:boxborderw=10"

                if caption_style_opt == "simple":
                    font_color_hex = "0xFFFFFF"
                    draw_border_w = 2
                    border_color_hex = "0x000000"
                    box_option = ""
                elif caption_style_opt == "mozi":
                    font_color_hex = "0xFFFFFF"
                    draw_border_w = 3
                    border_color_hex = "0x00FF00"
                    box_option = ":box=1:boxcolor=black@0.7:boxborderw=10"
                elif caption_style_opt == "karaoke":
                    font_color_hex = "0xFFFF00"
                    draw_border_w = 3
                    border_color_hex = "0x000000"
                    box_option = ":box=1:boxcolor=black@0.7:boxborderw=12"
                    draw_font_size = caption_font_size + 4
                elif caption_style_opt == "beasty":
                    font_color_hex = "0xFFFFFF"
                    draw_border_w = 5
                    border_color_hex = "0x000000"
                    box_option = ""
                    draw_font_size = caption_font_size + 6
                elif caption_style_opt == "highlighter":
                    font_color_hex = "0x000000"
                    draw_border_w = 0
                    border_color_hex = "0x000000"
                    box_option = ":box=1:boxcolor=yellow@0.9:boxborderw=15"
                    draw_font_size = caption_font_size + 2
                elif caption_style_opt == "blur_switch":
                    font_color_hex = "0xFFFFFF"
                    draw_border_w = 2
                    border_color_hex = "0x000000"
                    box_option = ":box=1:boxcolor=0x111111@0.85:boxborderw=14"
                    draw_font_size = caption_font_size + 4
                elif caption_style_opt == "grow":
                    font_color_hex = "0xFFFFFF"
                    draw_border_w = 4
                    border_color_hex = "0x000000"
                    box_option = ":box=1:boxcolor=black@0.6:boxborderw=10"
                    draw_font_size = caption_font_size + 6
                elif caption_style_opt == "popline":
                    font_color_hex = "0xFFFFFF"
                    draw_border_w = 3
                    border_color_hex = "0x00FFFF"
                    box_option = ":box=1:boxcolor=black@0.7:boxborderw=10"
                    draw_font_size = caption_font_size + 2
                elif caption_style_opt == "bottom_bold":
                    font_color_hex = "0xFFFFFF"
                    draw_border_w = 3
                    border_color_hex = "0x000000"
                    box_option = ":box=1:boxcolor=black@0.5:boxborderw=10"
                    draw_font_size = caption_font_size + 4

                border_option = f":borderw={draw_border_w}:bordercolor={border_color_hex}" if draw_border_w > 0 else ""
                filters.append(
                    f"[{current_label}]drawtext=textfile='{_escape_filter_path(caption_paths[index])}'"
                    f"{fontfile_option}:fontcolor={font_color_hex}:fontsize={draw_font_size}"
                    f"{border_option}{box_option}"
                    f":x=(w-text_w)/2:y={draw_y_expr}:text_shaping=1"
                    f":enable='between(t,{start_time:.3f},{end_time:.3f})'[{next_label}]"
                )

            current_label = next_label
        filters.append(f"[{current_label}]format=yuv420p[video]")
        audio_filters = []
        voice_label = "voice_delayed"
        if intro_duration:
            audio_filters.append(f"[{audio_index}:a]adelay={round(intro_duration * 1000)}:all=1[{voice_label}]")
        else:
            audio_filters.append(f"[{audio_index}:a]anull[{voice_label}]")

        if use_music:
            raw_vol = float(music_volume) if music_volume is not None else 1.0
            final_volume = round(max(1.50, raw_vol * 1.5), 2)
            print(f"[DEBUG] Music volume applied: {final_volume}")

            if story_mode_music and section_music_inputs:
                sec_labels = []
                for idx_m, sec_info in enumerate(section_music_inputs):
                    lbl_m = f"sec_m_{idx_m}"
                    in_i = sec_info["input_idx"]
                    dur_m = sec_info["duration"]
                    del_m = round(sec_info["start_time"] * 1000)
                    fade_d = min(0.3, dur_m / 2.0)
                    filters.append(
                        f"[{in_i}:a]atrim=0:{dur_m:.4f},"
                        f"afade=t=in:st=0:d={fade_d:.3f},"
                        f"afade=t=out:st={max(0, dur_m - fade_d):.3f}:d={fade_d:.3f},"
                        f"adelay={del_m}:all=1[{lbl_m}]"
                    )
                    sec_labels.append(f"[{lbl_m}]")
                
                filters.append(
                    f"{''.join(sec_labels)}amix=inputs={len(sec_labels)}:duration=first:dropout_transition=1[story_bg_raw]"
                )
                filters.append(f"[story_bg_raw]volume={final_volume:.2f}[music]")
            else:
                audio_filters.append(f"[{music_index}:a]volume={final_volume:.2f}[music]")

            audio_filters.append(
                f"[{voice_label}][music]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[mixed]"
            )
            audio_label = "mixed"
        else:
            audio_label = voice_label
        audio_tail = []
        if outro_duration:
            audio_tail.append(f"apad=pad_dur={outro_duration:.3f}")
        audio_tail.append(f"atrim=duration={final_video_duration:.6f}")
        audio_filters.append(f"[{audio_label}]{','.join(audio_tail)}[audio]")
        print(f"[DEBUG] FFmpeg Audio Filter: {';'.join(audio_filters)}")
        filters.extend(audio_filters)

        filter_script_path = temp_path / "filter_complex.txt"
        filter_script_path.write_text(";\n".join(filters), encoding="utf-8")

        cmd.extend([
            "-filter_complex_script", str(filter_script_path),
            "-map", "[video]", "-map", "[audio]",
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-t", f"{final_video_duration:.6f}", output_path,
        ])

        print("   [RENDER] Rendering base video with FFmpeg...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"   [ERROR] FFmpeg Error: {result.stderr}")
            raise Exception(result.stderr)
        
        print(f"   [OK] Video saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"[ERROR] Simple Engine Error: {e}")
        raise
    finally:
        if temporary_directory:
            temporary_directory.cleanup()