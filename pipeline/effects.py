import random

KEN_BURNS_PATTERNS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "diagonal", "rotate_slow"]
TRANSITIONS = ["fade", "slide_left", "slide_right", "zoom_in", "wipe", "circle"]
COLOR_FILTERS = ["none", "warm", "cool", "vintage", "high_contrast", "cinematic"]
VIGNETTE_OPTIONS = [True, False]
CAPTION_STYLES = ["bottom_center", "bottom_bold", "top_center", "karaoke_highlight"]


def pick_random_effects() -> dict:
    return {
        "ken_burns_pattern": random.choice(KEN_BURNS_PATTERNS),
        "transition": random.choice(TRANSITIONS),
        "color_filter": random.choice(COLOR_FILTERS),
        "vignette": random.choice(VIGNETTE_OPTIONS),
        "caption_style": random.choice(CAPTION_STYLES),
    }
