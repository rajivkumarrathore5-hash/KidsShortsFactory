import logging
from pathlib import Path
import sys
import requests

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


def generate_audio_indicf5(
    text,
    output_path,
    ref_audio_path=None,
    ref_text=None,
    speed=None,
):
    text = (text or "").strip()
    if not text:
        raise ValueError("Gemini script is empty. Cannot synthesize.")

    reference_audio = Path(ref_audio_path or INDICF5_REFERENCE_AUDIO or DEFAULT_REFERENCE_AUDIO)

    if not reference_audio.is_file():
        raise FileNotFoundError(
            "Reference voice not found at input/kid_voice.wav. "
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

    # FIX 1: Debug log & print first 50 chars of both Gemini script ('text') and reference transcript ('ref_text')
    safe_text_preview = text[:50].encode(sys.stdout.encoding or "utf-8", errors="backslashreplace").decode(sys.stdout.encoding or "utf-8", errors="replace")
    safe_ref_preview = ref_text[:50].encode(sys.stdout.encoding or "utf-8", errors="backslashreplace").decode(sys.stdout.encoding or "utf-8", errors="replace")
    print(f"[DEBUG] IndicF5 text (Gemini script first 50): {safe_text_preview!r}")
    print(f"[DEBUG] IndicF5 ref_text (Reference transcript first 50): {safe_ref_preview!r}")
    LOGGER.debug("IndicF5 text (first 50): %r", text[:50])
    LOGGER.debug("IndicF5 ref_text (first 50): %r", ref_text[:50])

    # Validation: Gemini script must not equal reference transcript
    if text == ref_text or text.strip() == ref_text.strip():
        raise ValueError(
            "Gemini script ('text') and reference transcript ('ref_text') are identical! "
            "The reference transcript must ONLY be used to clone the voice, NOT be spoken as scene text."
        )

    if len(text) < 5:
        raise ValueError("Gemini script too short.")
    selected_speed = INDICF5_SPEED if speed is None else float(speed)
    if not 0.5 <= selected_speed <= 2.0:
        raise ValueError("IndicF5 speed must be between 0.5 and 2.0.")

    if not is_server_running():
        raise ConnectionError(
            "IndicF5 server is not responding at "
            f"{HEALTH_URL}. Start it with pipeline.server_control.start_server()."
        )

    payload = {
        "text": text,
        "ref_audio_path": str(reference_audio.resolve()),
        "ref_text": ref_text,
        "speed": selected_speed,
    }
    LOGGER.debug(
        "IndicF5 request mapping: text=Gemini script (%d chars), "
        "ref_audio_path=voice reference, ref_text=reference transcript (%d chars), "
        "script_matches_transcript=%s",
        len(payload["text"]),
        len(payload["ref_text"]),
        payload["text"] == payload["ref_text"],
    )
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
    print(f"IndicF5 audio saved: {output}")
    return str(output)
