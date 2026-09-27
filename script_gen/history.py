import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path


CHARACTERS = ["Bal Krishna", "Bal Hanuman", "Bal Ganesh", "Shri Ram", "Shiv Ji"]
THEMES = ["Devotion", "Family", "Kindness", "Blessing", "Childhood"]
HISTORY_PATH = Path(__file__).resolve().parent.parent / "generated_scripts.json"
MAX_GENERATION_ATTEMPTS = 3


def _load_history():
    if not HISTORY_PATH.exists():
        return []

    with HISTORY_PATH.open(encoding="utf-8") as history_file:
        history = json.load(history_file)

    if not isinstance(history, list) or any(
        not isinstance(entry, dict)
        or not isinstance(entry.get("character"), str)
        or not isinstance(entry.get("theme"), str)
        or not isinstance(entry.get("script"), str)
        for entry in history
    ):
        raise ValueError(f"Invalid script history format in {HISTORY_PATH}")
    return history


def _canonical_character(character):
    if not character:
        return None
    if not isinstance(character, str):
        raise ValueError("Character must be a non-empty string.")
    normalized = character.strip().casefold()
    for supported_character in CHARACTERS:
        if normalized == supported_character.casefold():
            return supported_character
        if normalized == supported_character.removeprefix("Bal ").casefold():
            return supported_character
    return character.strip()


def _canonical_theme(theme):
    if not theme:
        return None
    if not isinstance(theme, str):
        raise ValueError("Theme must be a non-empty string.")
    for supported_theme in THEMES:
        if theme.strip().casefold() == supported_theme.casefold():
            return supported_theme
    return theme.strip()


def _next_combination(history, character=None, theme=None):
    used = {(entry["character"], entry["theme"]) for entry in history}
    combination_count = len(CHARACTERS) * len(THEMES)
    preferred_character = _canonical_character(character)
    preferred_theme = _canonical_theme(theme)

    if preferred_character and preferred_theme:
        return preferred_character, preferred_theme

    ordered_combinations = []
    for offset in range(combination_count):
        rotation_index = (len(history) + offset) % combination_count
        character_index = rotation_index % len(CHARACTERS)
        theme_index = (
            rotation_index // len(CHARACTERS) + character_index
        ) % len(THEMES)
        combination = (CHARACTERS[character_index], THEMES[theme_index])
        if combination not in used:
            ordered_combinations.append(combination)

    if preferred_character and preferred_theme:
        preferred = (preferred_character, preferred_theme)
        if preferred in ordered_combinations:
            return preferred
    if preferred_character:
        for combination in ordered_combinations:
            if combination[0] == preferred_character:
                return combination
    if preferred_theme:
        for combination in ordered_combinations:
            if combination[1] == preferred_theme:
                return combination
    if ordered_combinations:
        return ordered_combinations[0]

    raise RuntimeError(
        f"All {combination_count} character/theme combinations have been used. "
        f"Archive or clear {HISTORY_PATH} to start a new rotation."
    )


def _normalize_script(script):
    normalized = unicodedata.normalize("NFKC", script).casefold()
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _build_prompt(character, theme, duration, history, theme_config=None, scene_count=4):
    previous_scripts = "\n".join(
        f"- {entry['script']}" for entry in history if entry["script"].strip()
    )
    if not previous_scripts:
        previous_scripts = "None yet."

    theme_config = theme_config or {}
    output_character = character.removeprefix("Bal ")
    theme_name = theme_config.get("theme", theme)
    mood = theme_config.get("mood", "devotional and child-friendly")
    setting = theme_config.get("setting", "a respectful devotional setting")
    base_style = theme_config.get("base_style", "cinematic devotional art")
    visual_style = theme_config.get("visual_style", "cinematic devotional art")
    schema = {
        "character": output_character,
        "base_style": base_style,
        "scenes": [
            {
                "text": f"Short spoken Hindi narration sentence for scene {index + 1}.",
                "visual_prompt": f"Detailed 60-100 word English image prompt for scene {index + 1}.",
            }
            for index in range(scene_count)
        ],
    }
    return f"""Generate a unique Hindi devotional short as valid JSON only.
Use exactly this JSON shape, with no Markdown fences or text outside the JSON:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Character: {character}
Theme: {theme_name}
Mood: {mood}
Setting: {setting}
Base visual style: {base_style}

Length: Exactly {scene_count} scenes, each with one concise spoken Hindi sentence, suitable for a {duration}-second short.
Target approximately {duration * 14} Hindi characters total across all scene text.

JSON Requirements:
1. "character": Must be exactly "{output_character}".
2. "base_style": Must be "{base_style}".
3. "scenes": Exactly {scene_count} scene objects. Each scene MUST have:
   - "text": Hindi narration text (spoken sentence).
   - "visual_prompt": A DETAILED English image generation prompt (60-100 words) optimized for AI image generators (Agnes AI / Cloudflare Flux).

CRITICAL VISUAL PROMPT REQUIREMENTS (for EACH scene's "visual_prompt"):
- Character Description: Include a specific detailed character description (e.g., "cute baby Krishna with blue skin, peacock feather, yellow dhoti, gold jewelry").
  MUST USE THE EXACT SAME CHARACTER DESCRIPTION ACROSS ALL SCENES in the video for strict visual consistency! Vary only action, mood, and camera angle.
- Action/Mood: Specify the action and emotional expression for the scene (e.g., "eating butter from a clay pot with a mischievous smile").
- Setting: Specify rich setting details (e.g., "traditional Indian kitchen with clay pots, warm golden sunlight streaming through a window").
- Style Keywords: Include style keywords: "3D render, Pixar-style, hyperrealistic, cinematic lighting, soft shadows, volumetric light, 8k, masterpiece, ultra-detailed, devotional art".
- Camera Angle: Specify camera perspective ("medium shot, eye level" or "close-up" or "wide shot").
- Aspect & Composition: Include "vertical composition, 9:16".

Language: Natural, child-friendly Hindi for "text". English for "visual_prompt".
Make this script completely different from previous scripts.

Previous scripts to avoid repeating:
{previous_scripts}
"""


def parse_structured_script(
    response,
    expected_character=None,
    theme_config=None,
    expected_scene_count=None,
):
    response = response.strip()
    if response.startswith("```"):
        response = re.sub(r"^```(?:json)?\s*|\s*```$", "", response, flags=re.IGNORECASE)
    try:
        data = json.loads(response)
    except json.JSONDecodeError as error:
        raise ValueError(f"Script provider returned invalid JSON: {error}") from error

    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        raise ValueError("Structured script must be a JSON object with a scenes array.")
    if expected_scene_count is not None and len(data["scenes"]) != expected_scene_count:
        raise ValueError(f"Structured script must contain exactly {expected_scene_count} scenes.")
    if not 3 <= len(data["scenes"]) <= 5:
        raise ValueError("Structured script must contain 3 to 5 scenes.")

    expected_name = _canonical_character(expected_character).removeprefix("Bal ") if expected_character else None
    character = data.get("character")
    if not isinstance(character, str) or not character.strip():
        raise ValueError("Structured script must include a character name.")
    if expected_name:
        returned_name = _canonical_character(character).removeprefix("Bal ")
        if returned_name.casefold() != expected_name.casefold():
            raise ValueError(f"Expected character '{expected_name}', got '{character}'.")
        character = expected_name

    theme_config = theme_config or {}
    returned_theme = data.get("theme", theme_config.get("theme", ""))
    mood = data.get("mood", theme_config.get("mood", ""))
    base_style = data.get("base_style", theme_config.get("base_style", ""))
    scenes = []
    for scene_number, scene in enumerate(data["scenes"], start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {scene_number} must be a JSON object.")
        scene_text = scene.get("text")
        visual_prompt = scene.get("visual_prompt", "")
        keywords = scene.get("visual_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        if not isinstance(scene_text, str) or not scene_text.strip():
            raise ValueError(f"Scene {scene_number} must have non-empty spoken text.")
        if not isinstance(visual_prompt, str) or not visual_prompt.strip():
            raise ValueError(f"Scene {scene_number} must have a non-empty visual_prompt.")
        scenes.append(
            {
                "text": scene_text.strip(),
                "visual_prompt": visual_prompt.strip(),
                "visual_keywords": [k.strip() for k in keywords if isinstance(k, str) and k.strip()],
            }
        )

    return {
        "character": character,
        "theme": returned_theme,
        "mood": mood,
        "base_style": base_style,
        "scenes": scenes,
    }


def spoken_text(script):
    return "\n".join(scene["text"] for scene in script["scenes"])


def _save_history(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=HISTORY_PATH.parent,
            suffix=".tmp",
            delete=False,
        ) as history_file:
            json.dump(history, history_file, ensure_ascii=False, indent=2)
            history_file.write("\n")
            temporary_path = Path(history_file.name)
        os.replace(temporary_path, HISTORY_PATH)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def generate_unique_script(
    generate_response,
    character=None,
    theme=None,
    duration=15,
    theme_config=None,
    scene_count=4,
):
    theme_config = theme_config or {}
    character = theme_config.get("character", character)
    theme = theme_config.get("theme", theme)
    history = _load_history()
    character, theme = _next_combination(history, character, theme)
    previous_scripts = set()
    for entry in history:
        old_script = entry["script"].strip()
        if not old_script:
            continue
        try:
            previous_spoken_text = spoken_text(
                parse_structured_script(old_script, expected_character=entry["character"])
            )
        except ValueError:
            previous_spoken_text = old_script
        previous_scripts.add(_normalize_script(previous_spoken_text))

    for _ in range(MAX_GENERATION_ATTEMPTS):
        response = generate_response(
            _build_prompt(character, theme, duration, history, theme_config, scene_count)
        )
        if not isinstance(response, str) or not response.strip():
            raise RuntimeError("The script provider returned an empty script.")
        try:
            script = parse_structured_script(
                response,
                expected_character=character,
                theme_config=theme_config,
                expected_scene_count=scene_count,
            )
        except ValueError:
            continue

        dialogue = spoken_text(script)
        if _normalize_script(dialogue) in previous_scripts:
            continue

        serialized_script = json.dumps(script, ensure_ascii=False, separators=(",", ":"))
        history.append(
            {
                "character": character,
                "theme": theme,
                "theme_id": theme_config.get("id"),
                "script": serialized_script,
            }
        )
        _save_history(history)
        return script

    raise RuntimeError(
        "The script provider repeated an existing script after "
        f"{MAX_GENERATION_ATTEMPTS} attempts; nothing was added to history."
    )


def get_script_metadata(script):
    if isinstance(script, dict):
        script = json.dumps(script, ensure_ascii=False, separators=(",", ":"))
    normalized_script = _normalize_script(script)
    for entry in reversed(_load_history()):
        if _normalize_script(entry["script"]) == normalized_script:
            return {"character": entry["character"], "theme": entry["theme"]}
    return {"character": "Unknown", "theme": "Unknown"}