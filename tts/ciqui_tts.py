import os
from TTS.api import TTS
import torch

# Path to your voice sample (Kids voice)
VOICE_SAMPLE_PATH = "input/kids_voice_sample.wav"  # 👈 Yahan apni voice sample rakhein

def generate_audio(text, output_path):
    # Check if GPU available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Load TTS model with voice cloning
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", 
              progress_bar=False).to(device)
    
    # Generate speech using voice sample
    tts.tts_to_file(
        text=text,
        file_path=output_path,
        speaker_wav=VOICE_SAMPLE_PATH,  # 👈 Voice clone
        language="hi"  # Hindi
    )
    return output_path