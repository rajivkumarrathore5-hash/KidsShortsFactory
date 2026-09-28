import logging
from pathlib import Path
import re
import subprocess
import sys
import requests

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from config import (
    INDICF5_REFERENCE_AUDIO,
    INDICF5_REFERENCE_TEXT,
    INDICF5_SPEED,
    INDICF5_SERVER_URL,
)

DEFAULT_REFERENCE_AUDIO = Path(
    r"C:\Users\91757\Downloads\KidsShortsFactory\input\kid_voice.wav"
)
DEFAULT_REFERENCE_TEXT = Path(
    r"C:\Users\91757\Downloads\KidsShortsFactory\input\kid_voice.txt"
)
SYNTHESIZE_URL = f"{INDICF5_SERVER_URL.rstrip('/')}/generate"
HEALTH_URL = f"{INDICF5_SERVER_URL.rstrip('/')}/health"
LOGGER = logging.getLogger(__name__)


def is_server_running():
    try:
        response = requests.get(HEALTH_URL, timeout=2)
        if response.status_code != 200:
            return False
        payload = response.json()
        return payload.get("status") == "ok" and payload.get("engine") == "indicf5"
    except (requests.RequestException, ValueError):
        return False


def sanitize_script_text(text: str, ref_text: str = None) -> str:
    """
    Sanitizes generated script text before sending to IndicF5 TTS.
    Removes any accidental reference transcript lines or phrases.
    """
    if not text:
        return ""

    cleaned = str(text).strip()

    # If reference text exists, explicitly strip it and its variations
    if ref_text and ref_text.strip():
        ref_clean = ref_text.strip()
        if ref_clean in cleaned:
            print("[IndicF5] Warning: Reference transcript detected in script text. Stripping it out.")
            cleaned = cleaned.replace(ref_clean, "")

    known_ref_phrases = [
        "काल हरा कष हरा दुःख हरा दरिद्र हरा सर्व रोग सर्व पाप हरा हर हर महादेव शंभु शंकर काल हरा कष हरा दुःख हरा दरिद्र हरा सर्व रोग सर्व पाप।",
        "काल हरा कष हरा दुःख हरा दरिद्र हरा सर्व रोग सर्व पाप हरा हर हर महादेव शंभु शंकर काल हरा कष हरा दुःख हरा दरिद्र हरा सर्व रोग सर्व पाप",
        "काल हरा कष हरा दुःख हरा दरिद्र हरा सर्व रोग सर्व पाप",
        "काल हरा कष हरा दुःख हरा दरिद्र हरा",
        "हर हर महादेव शंभु शंकर",
    ]
    for phrase in known_ref_phrases:
        if phrase in cleaned:
            print(f"[IndicF5] Warning: Reference phrase detected in script text. Stripping it out.")
            cleaned = cleaned.replace(phrase, "")

    # Clean up excess whitespace and blank lines
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return "\n".join(lines)


def get_audio_duration_seconds(audio_path: str) -> float:
    """
    Gets duration of audio file using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def generate_audio_indicf5(
    text,
    output_path,
    ref_audio_path=None,
    ref_text=None,
    speed=None,
):
    raw_text = (text or "").strip()
    if not raw_text:
        raise ValueError("Script text is empty. Cannot synthesize.")

    reference_audio = Path(ref_audio_path or INDICF5_REFERENCE_AUDIO or DEFAULT_REFERENCE_AUDIO)
    if not reference_audio.is_file():
        raise FileNotFoundError(
            f"Reference voice audio not found at {reference_audio}. "
            "Please place the WAV file before running the pipeline."
        )

    transcript_path = Path(INDICF5_REFERENCE_TEXT or DEFAULT_REFERENCE_TEXT)
    if ref_text is None:
        if not transcript_path.is_file():
            raise FileNotFoundError(
                f"IndicF5 reference transcript not found: {transcript_path}. "
                "Add the exact UTF-8 transcript in input/kid_voice.txt."
            )
        ref_text = transcript_path.read_text(encoding="utf-8")
    ref_text = ref_text.strip()
    if not ref_text:
        raise ValueError(f"IndicF5 reference transcript is empty: {transcript_path}")

    # Sanitize script text to ensure NO reference transcript is present in text
    sanitized_text = sanitize_script_text(raw_text, ref_text)
    if not sanitized_text or len(sanitized_text) < 5:
        raise ValueError("Sanitized script text is too short or empty after stripping.")

    # Distinct clear logging of what is being sent to IndicF5 server
    preview_text = sanitized_text[:100].replace("\n", " ")
    preview_ref = ref_text[:100].replace("\n", " ")
    print(f"[IndicF5] Sending text to IndicF5 ({len(sanitized_text)} chars): {preview_text}")
    print(f"[IndicF5] Sending ref_text to IndicF5 ({len(ref_text)} chars): {preview_ref}")
    LOGGER.info("Sending text to IndicF5: %r", preview_text)
    LOGGER.info("Sending ref_text to IndicF5: %r", preview_ref)

    # Validation: Script ('text') and reference transcript ('ref_text') must NEVER be identical
    if sanitized_text == ref_text or sanitized_text.strip() == ref_text.strip():
        raise ValueError(
            "Script ('text') and reference transcript ('ref_text') are identical! "
            "The reference transcript must ONLY be used to clone the voice, NOT be spoken as scene text."
        )

    selected_speed = INDICF5_SPEED if speed is None else float(speed)
    if not 0.5 <= selected_speed <= 2.0:
        raise ValueError("IndicF5 speed must be between 0.5 and 2.0.")

    if not is_server_running():
        raise ConnectionError(
            "IndicF5 server is not responding at "
            f"{HEALTH_URL}. Start it with pipeline.server_control.start_server()."
        )

    # Clean payload mapping with strict separation
    payload = {
        "text": sanitized_text,
        "ref_audio_path": str(reference_audio.resolve()),
        "ref_text": ref_text,
        "speed": selected_speed,
    }

    try:
        response = requests.post(SYNTHESIZE_URL, json=payload, timeout=(5, 600))
        response.raise_for_status()
    except requests.RequestException as error:
        detail = error
        if getattr(error, "response", None) is not None:
            try:
                detail = error.response.json().get("error", error)
            except ValueError:
                detail = error.response.text or error
        raise RuntimeError(f"IndicF5 synthesis request failed: {detail}") from error

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type != "audio/wav" or not response.content.startswith(b"RIFF"):
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text[:500]
        raise RuntimeError(f"IndicF5 server did not return WAV audio: {detail}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)

    # Verification: Validate generated audio file
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"IndicF5 audio file is empty or missing: {output}")

    duration = get_audio_duration_seconds(str(output))
    print(f"[IndicF5] Audio generated successfully: {output.name} (duration: {duration:.2f}s, size: {output.stat().st_size} bytes)")
    return str(output)
