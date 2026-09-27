from config import RENDER_ENGINE

def get_render_engine():
    if RENDER_ENGINE == "moviepy":
        from . import moviepy_engine
        return moviepy_engine.render_video
    elif RENDER_ENGINE == "ffmpeg":
        from . import ffmpeg_engine
        return ffmpeg_engine.render_video
    elif RENDER_ENGINE == "pil":
        from . import pil_engine
        return pil_engine.render_video
    elif RENDER_ENGINE == "simple":
        from . import simple_engine
        return simple_engine.render_video
    else:
        raise ValueError(f"Unknown RENDER_ENGINE: {RENDER_ENGINE}")