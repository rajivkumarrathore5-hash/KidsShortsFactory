from functools import partial
from pathlib import Path

from config import (
    INDICF5_REFERENCE_AUDIO,
    INDICF5_REFERENCE_TEXT,
    INDICF5_SPEED,
    TTS_PROVIDER,
)


def get_tts(
    provider=None,
    voice=None,
    pitch=None,
    rate=None,
    ref_audio_path=None,
    ref_text_path=None,
    speed=None,
):
    selected_provider = (provider or TTS_PROVIDER).strip().lower()
    if selected_provider != "indicf5":
        raise RuntimeError(
            f"Unsupported TTS provider '{selected_provider}'. Only 'indicf5' is supported."
        )

    from .indicf5_tts import generate_audio_indicf5

    project_root = Path(__file__).resolve().parents[1]
    reference_audio = Path(ref_audio_path or INDICF5_REFERENCE_AUDIO)
    transcript_path = Path(ref_text_path or INDICF5_REFERENCE_TEXT)
    if not reference_audio.is_absolute():
        reference_audio = project_root / reference_audio
    if not transcript_path.is_absolute():
        transcript_path = project_root / transcript_path
    if not reference_audio.is_file():
        raise RuntimeError(
            f"Reference voice audio not found at {reference_audio}. "
            "Please place the WAV file before running the pipeline."
        )
    if not transcript_path.is_file():
        raise RuntimeError(
            f"IndicF5 reference transcript not found at {transcript_path}. "
            "Add the exact UTF-8 transcript in input/kid_voice.txt."
        )
    ref_text = transcript_path.read_text(encoding="utf-8").strip()
    if not ref_text:
        raise RuntimeError(f"IndicF5 reference transcript is empty: {transcript_path}")

    return partial(
        generate_audio_indicf5,
        ref_audio_path=str(reference_audio),
        ref_text=ref_text,
        speed=INDICF5_SPEED if speed is None else speed,
    )
