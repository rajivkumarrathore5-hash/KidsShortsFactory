import re
from pathlib import Path

from visuals.pexels import get_images as get_pexels_images
from .ai_images import generate_agnes_image, generate_cloudflare_image


def compute_dimensions(aspect_ratio):
    match = re.fullmatch(r"(\d+):(\d+)", str(aspect_ratio).strip())
    if not match:
        return 1080, 1920
    ratio_width, ratio_height = map(int, match.groups())
    if ratio_width == 0 or ratio_height == 0:
        return 1080, 1920
    if ratio_width <= ratio_height:
        width = 1080
        height = round(1080 * ratio_height / ratio_width)
    else:
        height = 1080
        width = round(1080 * ratio_width / ratio_height)
    width = max(2, width + (width % 2))
    height = max(2, height + (height % 2))
    return width, height


def _scene_prompt(scene, theme):
    if theme is None:
        raise ValueError("Theme configuration is None. Cannot generate visual prompts.")
    scene_visual = scene.get("visual_prompt", "").strip()
    if scene_visual:
        return scene_visual
    keywords = ", ".join(scene.get("visual_keywords", []))
    base_prompt = (
        f"{theme['base_style']}. Visual style: {theme['visual_style']}. "
        f"Keep the same character consistent across every scene: {theme['character']}. "
        f"Setting and mood: {theme['setting']}; {theme['mood']}. "
        f"Scene: {scene_visual}. Visual keywords: {keywords}. "
        "Portrait 9:16 composition, family-friendly devotional illustration"
    )
    suffix = ", 3D render, hyperrealistic, cinematic lighting, soft shadows, 8k, masterpiece"
    return base_prompt + suffix


def get_scene_images(
    scenes,
    output_dir,
    theme,
    aspect_ratio="9:16",
    visual_source="ai",
    seed=None,
    ai_image_provider="agnes",
    image_provider=None,
):
    if theme is None:
        raise ValueError("Theme configuration is None. Cannot fetch scene images.")
    scene_directory = Path(output_dir)
    scene_directory.mkdir(parents=True, exist_ok=True)

    width, height = compute_dimensions(aspect_ratio)
    print(f"[IMG] Target image dimensions for aspect ratio '{aspect_ratio}': {width}x{height}")

    source = visual_source.strip().lower()
    if source not in {"ai", "pexels"}:
        raise ValueError("VISUAL_SOURCE must be 'ai' or 'pexels'.")

    total_scenes = len(scenes)
    if source == "pexels":
        return get_pexels_images(
            scenes,
            scene_directory,
            character=theme["character"],
            theme=theme["theme"],
            base_style=theme["base_style"],
            visual_style=theme["visual_style"],
            scene_count=total_scenes,
            width=width,
            height=height,
        )

    images = []
    for index, scene in enumerate(scenes, start=1):
        image_path = scene_directory / f"scene_{index}.jpg"
        prompt = _scene_prompt(scene, theme)
        success = False

        # LAYER 1: Agnes AI
        print(f"[IMG] Trying Agnes AI (scene {index}/{total_scenes}, size: {width}x{height})...")
        try:
            generate_agnes_image(prompt, image_path, width=width, height=height, seed=seed)
            print(f"[IMG] Agnes AI success (scene {index}/{total_scenes})")
            success = True
        except Exception as agnes_err:
            print(f"[FALLBACK] Agnes AI failed: {agnes_err}, moving to Cloudflare...")

        # LAYER 2: Cloudflare Workers AI
        if not success:
            print(f"[IMG] Trying Cloudflare AI (scene {index}/{total_scenes}, size: {width}x{height})...")
            try:
                generate_cloudflare_image(prompt, image_path, width=width, height=height, seed=seed)
                print(f"[IMG] Cloudflare fallback success (scene {index}/{total_scenes})")
                success = True
            except Exception as cf_err:
                print(f"[FALLBACK] Cloudflare failed: {cf_err}, moving to Pexels...")

        # LAYER 3: Pexels
        if not success:
            print(f"[IMG] Trying Pexels fallback (scene {index}/{total_scenes})...")
            fallback = get_pexels_images(
                [scene],
                scene_directory,
                character=theme["character"],
                theme=theme["theme"],
                base_style=theme["base_style"],
                visual_style=theme["visual_style"],
                start_index=index,
                scene_count=1,
                width=width,
                height=height,
            )
            if fallback:
                image_path = Path(fallback[0])
                print(f"[IMG] Pexels fallback success (scene {index}/{total_scenes})")
                success = True

        images.append(str(image_path))

    return images
