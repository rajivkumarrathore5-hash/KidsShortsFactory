from config import SCRIPT_PROVIDER

def get_script(
    character=None,
    theme=None,
    duration=15,
    theme_config=None,
    scene_count=4,
    video_mode="short",
):
    if SCRIPT_PROVIDER == "gemini":
        from . import gemini
        return gemini.generate_script(
            character, theme, duration,
            theme_config=theme_config,
            scene_count=scene_count,
            video_mode=video_mode,
        )
    elif SCRIPT_PROVIDER == "groq":
        from . import groq
        return groq.generate_script(
            character, theme, duration,
            theme_config=theme_config,
            scene_count=scene_count,
            video_mode=video_mode,
        )
    else:
        raise ValueError("Unknown SCRIPT_PROVIDER")
