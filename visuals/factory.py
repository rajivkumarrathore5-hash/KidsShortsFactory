from config import VISUAL_PROVIDER

def get_visual():
    if VISUAL_PROVIDER == "pexels":
        from . import pexels
        return pexels.get_images
    elif VISUAL_PROVIDER == "pixabay":
        from . import pixabay
        return pixabay.get_video
    else:
        raise ValueError("Unknown VISUAL_PROVIDER")
