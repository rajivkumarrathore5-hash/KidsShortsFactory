from config import PLATFORMS, YOUTUBE_PROVIDER, FACEBOOK_PROVIDER, INSTAGRAM_PROVIDER

def upload_to_platforms(video_path, title=None, description=None, script=None, theme=None, character=None):
    results = {}
    if "youtube" in PLATFORMS:
        if YOUTUBE_PROVIDER == "api":
            from .youtube import api_uploader as yt
        else:
            from .youtube import internal_uploader as yt
        if YOUTUBE_PROVIDER == "api":
            results['youtube'] = yt.upload(
                video_path, title=title, description=description, script=script, theme=theme, character=character
            )
        else:
            results['youtube'] = yt.upload(video_path, title, description)
    if "facebook" in PLATFORMS:
        if FACEBOOK_PROVIDER == "graph_api":
            from .facebook import graph_api as fb
        else:
            from .facebook import selenium_uploader as fb
        if FACEBOOK_PROVIDER == "graph_api":
            results['facebook'] = fb.upload(
                video_path, title=title, description=description, script=script, theme=theme, character=character
            )
        else:
            results['facebook'] = fb.upload(video_path, title, description)
    if "instagram" in PLATFORMS:
        if INSTAGRAM_PROVIDER == "graph_api":
            from .instagram import graph_api as ig
        elif INSTAGRAM_PROVIDER == "instagrapi":
            from .instagram import instagrapi_uploader as ig
        else:
            from .instagram import selenium_uploader as ig
        results['instagram'] = ig.upload(video_path, title, description)
    return results
