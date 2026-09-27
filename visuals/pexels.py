import requests
import re
from pathlib import Path
from config import get_secret
from PIL import Image, ImageOps

SCENE_TERMS = {
    "माखन": "butter",
    "फूल": "flower garden",
    "गिलहरी": "squirrel",
    "पेड़": "tree",
    "मोर": "peacock",
    "नदी": "river",
    "चाँद": "moon night",
    "चांद": "moon night",
    "मिट्टी": "clay toys",
    "खेल": "children playing",
    "माँ": "mother and child",
    "माता": "mother and child",
    "बंदर": "monkey",
    "फल": "fruit",
    "मंदिर": "temple",
    "दोस्त": "children friends",
    "मदद": "helping hands",
    "दया": "kindness children",
}
CHARACTER_TERMS = {
    "krishna": "Krishna Indian devotional art",
    "bal krishna": "Krishna Indian devotional art",
    "radha and krishna": "Radha Krishna Vrindavan devotional art",
    "hanuman": "Hanuman Indian devotional art",
    "bal hanuman": "Hanuman Indian devotional art",
    "ganesh": "Ganesha Indian devotional art",
    "bal ganesh": "Ganesha Indian devotional art",
    "shri ram": "Rama Indian devotional art",
    "ram and sita": "Rama Sita Ayodhya devotional art",
    "maa durga": "Durga Shakti devotional art",
    "maa kali": "Kali Shakti devotional art",
    "maa lakshmi": "Lakshmi lotus devotional art",
    "lord jagannath, balabhadra and subhadra": "Jagannath Puri devotional art",
    "jagannath, balabhadra and subhadra": "Jagannath Puri devotional art",
    "shiv ji": "Shiva Indian devotional art",
    "shiv and parvati": "Shiva Parvati Kailash devotional art",
}


def _legacy_scene_keywords(script, scene_count):
    lowered = script.casefold()
    matched = [term for word, term in SCENE_TERMS.items() if word in lowered]
    if not matched:
        matched = re.findall(r"[A-Za-z]{3,}", script)
    return [
        {"visual_keywords": matched[index:index + 3] or ["kids cartoon scene"]}
        for index in range(0, max(len(matched), 1), 3)
    ][:scene_count]


def _save_gradient(path, scene_index, width=1080, height=1920):
    colors = [
        ("#174c64", "#be638b"),
        ("#315c42", "#d39b53"),
        ("#4c356f", "#e07a52"),
        ("#165f5d", "#bb6951"),
    ]
    dark, light = colors[(scene_index - 1) % len(colors)]
    gradient = Image.linear_gradient("L").resize((width, height))
    ImageOps.colorize(gradient, black=dark, white=light).save(path, quality=90)


def get_images(
    scenes,
    output_dir,
    character="Krishna",
    theme="Devotion",
    scene_count=None,
    base_style="",
    visual_style="",
    start_index=1,
    width=1080,
    height=1920,
):
    api_key = get_secret("PEXELS_API_KEY")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    if isinstance(scenes, str):
        scene_data = _legacy_scene_keywords(scenes, scene_count or 1)
    else:
        scene_data = list(scenes)
    if scene_count is not None:
        scene_data = scene_data[:scene_count]

    url = "https://api.pexels.com/v1/search"
    downloaded = []
    character_query = CHARACTER_TERMS.get(character.casefold(), character)
    orientation = "portrait" if height > width else ("square" if height == width else "landscape")
    for scene_offset, scene in enumerate(scene_data):
        scene_index = start_index + scene_offset
        keywords = scene.get("visual_keywords", []) if isinstance(scene, dict) else []
        keywords = [keyword.strip() for keyword in keywords if isinstance(keyword, str) and keyword.strip()]
        scene_setting = scene.get("visual_prompt", "") if isinstance(scene, dict) else ""
        query_terms = [character_query, theme, *keywords]
        if scene_setting:
            query_terms.extend(re.findall(r"[A-Za-z]{3,}", scene_setting)[:5])
        if visual_style:
            query_terms.extend(re.findall(r"[A-Za-z]{3,}", visual_style)[:3])
        query = ", ".join(dict.fromkeys(term for term in query_terms if term))
        image_path = output_path / f"scene_{scene_index}.jpg"
        failure = None

        if not api_key:
            failure = "PEXELS_API_KEY is missing"
        else:
            try:
                response = requests.get(
                    url,
                    headers={"Authorization": api_key},
                    params={"query": query, "per_page": 1, "orientation": orientation},
                    timeout=20,
                )
                response.raise_for_status()
                photos = response.json().get("photos", [])
                if not photos:
                    raise ValueError("Pexels returned no matching photos")

                photo = photos[0]
                sources = photo.get("src", {})
                image_url = sources.get("portrait") or sources.get("large2x") or sources.get("large")
                if not image_url:
                    raise ValueError(f"Pexels photo {photo.get('id')} has no portrait image URL")

                image_response = requests.get(image_url, timeout=30)
                image_response.raise_for_status()
                temporary_path = output_path / f"scene_{scene_index}.download"
                temporary_path.write_bytes(image_response.content)
                try:
                    with Image.open(temporary_path) as source_image:
                        image = ImageOps.fit(
                            source_image.convert("RGB"),
                            (width, height),
                            method=Image.Resampling.LANCZOS,
                            centering=(0.5, 0.5),  # Crop from CENTER (not top)
                        )
                        image.save(image_path, format="JPEG", quality=92)
                finally:
                    temporary_path.unlink(missing_ok=True)
            except (requests.RequestException, ValueError, OSError) as error:
                failure = str(error)

        if failure:
            print(f"[WARNING] Pexels scene {scene_index} failed ({query}): {failure}")
            _save_gradient(image_path, scene_index, width=width, height=height)
            print(f"      → scene_{scene_index}.jpg (gradient fallback)")
        else:
            print(f"      → scene_{scene_index}.jpg ({', '.join(keywords)})")
        downloaded.append(str(image_path))

    return downloaded