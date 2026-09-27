"""
Wrapper to re-export tts.indicf5_tts for compatibility with pipeline/tts/ path.
"""
from tts.indicf5_tts import (
    generate_audio_indicf5,
    is_server_running,
    SYNTHESIZE_URL,
    HEALTH_URL,
)

__all__ = [
    "generate_audio_indicf5",
    "is_server_running",
    "SYNTHESIZE_URL",
    "HEALTH_URL",
]
