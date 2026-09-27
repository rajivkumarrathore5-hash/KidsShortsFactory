import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import *

def render_video(audio_path, text, output_path, visual_url=None, duration=18):
    try:
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        
        # Create PIL image with text
        img = Image.new('RGB', (1080, 1920), color=(50, 150, 255))
        draw = ImageDraw.Draw(img)
        
        # Font
        try:
            font = ImageFont.truetype("arial.ttf", 80)
        except:
            try:
                font = ImageFont.truetype("C:\\Windows\\Fonts\\Arial.ttf", 80)
            except:
                font = ImageFont.load_default()
        
        # Split text into multiple lines
        lines = text.split('\n')
        y_position = 1400
        for line in lines:
            words = line.split()
            new_line = ""
            for word in words:
                if len(new_line + " " + word) < 50:
                    new_line += " " + word
                else:
                    draw.text((540, y_position), new_line, fill='yellow', font=font, 
                              anchor='mm', stroke_width=4, stroke_fill='black')
                    y_position += 100
                    new_line = word
            if new_line:
                draw.text((540, y_position), new_line, fill='yellow', font=font, 
                          anchor='mm', stroke_width=4, stroke_fill='black')
                y_position += 100
        
        # Convert PIL to numpy array
        img_np = np.array(img)
        
        # ✅ Create clip with explicit fps
        clip = ImageClip(img_np, fps=24).set_duration(audio_duration)
        clip = clip.set_audio(audio_clip)
        
        # ✅ Write video with explicit fps
        clip.write_videofile(
            output_path,
            fps=24,              # Explicit FPS
            codec='libx264',
            audio_codec='aac',
            threads=4,
            verbose=False,
            logger=None
        )
        
        return output_path
        
    except Exception as e:
        print(f"❌ PIL Engine Error: {e}")
        raise