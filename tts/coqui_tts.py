import os
from TTS.api import TTS
import torch

# 👇 Aapki voice sample ka path (exact filename check kar lein)
VOICE_SAMPLE_PATH = "input/kids_voice_sample.wav"  # Agar filename alag hai toh yahan change karein

def generate_audio(text, output_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # XTTS v2 model load karein (voice cloning ke liye)
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2",
              progress_bar=False).to(device)
    
    # Voice sample ke hisaab se audio generate karein
    tts.tts_to_file(
        text=text,
        file_path=output_path,
        speaker_wav=VOICE_SAMPLE_PATH,  # 👈 Aapki voice clone
        language="hi"  # Hindi
    )
    return output_path