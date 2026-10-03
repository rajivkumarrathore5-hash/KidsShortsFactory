import json
import random
import re
from config import get_secret


def _llm_generate_text(prompt: str) -> str:
    """
    Generate text using the 3-layer fallback chain with persisted last successful model.
    """
    from script_gen.gemini import generate_text_with_fallback
    return generate_text_with_fallback(prompt, is_metadata=True)


def pick_random_title_language() -> str:
    """
    Randomly pick title language ('hindi' or 'hinglish'). Pure English is disabled.
    """
    chosen = random.choice(["hindi", "hinglish"])
    print(f"[META] Title language: {chosen}")
    return chosen


def validate_and_format_title(raw_title: str, character: str = None) -> str:
    """
    Validate and format title to be strictly <= 100 chars, ensuring #shorts is present.
    Logs: [META] Title length: <N>/100 characters
    """
    title = str(raw_title).strip()

    # Ensure #shorts is present in hashtags (case-insensitive check)
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"

    if len(title) > 100:
        words = title.split()
        hashtags = [w for w in words if w.startswith("#")]
        non_hashtags = [w for w in words if not w.startswith("#")]

        if not any(h.lower() == "#shorts" for h in hashtags):
            hashtags.append("#shorts")

        hashtag_str = " " + " ".join(hashtags)
        max_non_hashtag_len = 100 - len(hashtag_str)

        if max_non_hashtag_len > 10:
            main_text = " ".join(non_hashtags)
            if len(main_text) > max_non_hashtag_len:
                main_text = main_text[:max_non_hashtag_len].rstrip()
            title = (main_text + hashtag_str).strip()
        else:
            title = title[:100].strip()

    if len(title) > 100:
        title = title[:100].strip()

    print(f"[META] Title length: {len(title)}/100 characters")
    return title


def generate_youtube_metadata(script_text, theme=None, character=None, title_language=None, video_mode="short"):
    """
    Generates refined YouTube Shorts title, description, and tags using the 3-layer LLM fallback chain.
    Supports 'short' and 'story' video modes.
    Enforces Hindi (Devanagari) or Hinglish (Roman Hindi) with viral hooks.
    """
    chosen_lang = title_language or pick_random_title_language()
    if chosen_lang not in ("hindi", "hinglish"):
        chosen_lang = random.choice(["hindi", "hinglish"])

    theme_str = theme or "Devotion & Moral"
    char_str = character or "Indian Mythology"

    lang_instructions = {
        "hindi": (
            "Write Title & Description STRICTLY in Hindi (Devanagari script). "
            "Use viral curiosity hook or question. "
            "Example Title: 'छोटे कृष्ण की माखन चोरी का अनोखा रहस्य! 🧈 #shorts #viral #krishna #bhakti'. "
            "Call-To-Action: '🙏 ऐसी ही दिव्य और पावन भक्ति कथाओं के लिए सब्सक्राइब करें!'"
        ),
        "hinglish": (
            "Write Title & Description in Hinglish (Conversational Roman Hindi). "
            "Use viral curiosity hook or question. "
            "Example Title: 'Chote Krishna ki Makhan Chori Ka Adbhut Rahasya! 🧈 #shorts #viral #krishna #bhakti'. "
            "Call-To-Action: '🙏 Daily bhakti aur anokhi kahaniyo ke liye channel ko subscribe karein!'"
        ),
    }
    selected_lang_rule = lang_instructions.get(chosen_lang, lang_instructions["hindi"])

    mode_rule = ""
    if video_mode == "story":
        mode_rule = (
            "VIDEO MODE IS 'STORY':\n"
            "- Title MUST feature the suspenseful story hook / question (e.g. 'कृष्ण ने गोवर्धन पर्वत कैसे उठाया? 🏔️ #shorts #viral #krishna' or 'Krishna ne Govardhan Parvat Kaise Uthaya? 🏔️ #shorts #viral #krishna').\n"
            "- Description MUST explicitly highlight the moral/spiritual lesson of the story in 2-3 lines before hashtags.\n"
            "- Tags MUST include story narrative keywords (e.g. story, kahani, moral story, spiritual lesson).\n"
        )

    prompt = f"""
You are an expert YouTube Shorts creator for Indian devotional and moral stories.
Generate highly engaging, trending, viral YouTube Shorts metadata based on the following script:

Script:
{script_text}

Theme: {theme_str}
Character: {char_str}
Video Mode: {video_mode.upper()}
Target Language: {chosen_lang.upper()} (ONLY HINDI OR HINGLISH, NO PURE ENGLISH)

CRITICAL RULES:
- DO NOT write title in English. Use ONLY Hindi (Devanagari) or Hinglish (Roman script Hindi).
- The title must be viral, exciting, and curiosity-inducing.

LANGUAGE RULES:
{selected_lang_rule}

{mode_rule}
1. YOUTUBE TITLE RULES:
- MUST be within 95 characters total.
- Structure: [Viral Hook/Question] + [Character/Theme] + [1-2 Emojis] + [Hashtags]
- Required hashtags: ALWAYS include #shorts and #viral, plus 1-2 theme-specific hashtags (e.g., #krishna, #hanuman, #shiv, #ganesh, #jagannath, #durga, #lakshmi, #ram, #radha)
- Emojis: Include 1-2 relevant emojis (🙏, 🕉️, 🦚, 🪔, 🐒, 🐘, 🧈, 🏔️, etc.)

2. YOUTUBE DESCRIPTION RULES:
- Engaging summary of the video story and its moral lesson in {chosen_lang.upper()}.
- Include a clear call-to-action in {chosen_lang.upper()}.
- Include 5-10 hashtags at the END of the description:
  Always: #shorts #viral #bhakti
  Theme-specific: e.g. #krishna #radha #hanuman #shiv #ganesh #durga #lakshmi #ram
  Extra: #devotional #hindugods #aibhakti #3dart #moralstories #story

3. YOUTUBE TAGS RULES:
- Return 10-15 tags as a JSON array of string tags.
- Include BOTH Hindi (Devanagari script) and Hinglish versions (e.g. ["कृष्ण", "krishna", "हनुमान", "hanuman", "भक्ति", "bhakti", "shorts", "viral", "devotional", "hindu gods", "ai bhakti", "3d animation", "moral stories"]).
- Include generic tags: shorts, viral, devotional, hindu gods, ai bhakti, 3d animation, moral stories, hindi story.
- Include theme/character-specific tags.

Respond strictly in valid JSON format with three fields:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}

Output ONLY valid JSON.
"""

    raw_response = _llm_generate_text(prompt)
    title = None
    description = None
    tags = None

    if raw_response:
        try:
            cleaned = raw_response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()

            data = json.loads(cleaned)
            if isinstance(data, dict):
                title = data.get("title")
                description = data.get("description")
                tags = data.get("tags")
        except Exception as e:
            print(f"[WARNING] Failed to parse YouTube metadata JSON: {e}")

    # Fallback title if generation failed
    first_line = next((line.strip() for line in script_text.splitlines() if line.strip()), "Kids Story")
    keyword = character or theme or "Bhakti"
    char_tag = keyword.lower().replace(" ", "")

    if not title or len(str(title).strip()) == 0:
        if chosen_lang == "hindi":
            title = f"✨ बाल {keyword} की पावन कथा 🧈 #shorts #viral #{char_tag} #bhakti"
        else:
            title = f"✨ Chote {keyword} Ki Adbhut Kahani 🧈 #shorts #viral #{char_tag} #bhakti"

    # Validate and format title length
    formatted_title = validate_and_format_title(title, character=character)

    # Fallback description if generation failed
    if not description or len(str(description).strip()) == 0:
        cta_map = {
            "hindi": "🙏 दैनिक भक्ति और नैतिक कहानियों के लिए सब्सक्राइब करें!",
            "english": "🙏 Subscribe for daily bhakti & moral stories!",
            "hinglish": "🙏 Daily bhakti & moral stories ke liye subscribe karein!",
        }
        cta = cta_map.get(chosen_lang, cta_map["english"])
        description = (
            f"{script_text[:350]}\n\n"
            f"{cta}\n\n"
            f"#shorts #viral #bhakti #{char_tag} #devotional #hindugods #aibhakti #3dart #moralstories"
        )
    description = str(description).strip()[:5000]

    # Fallback tags if generation failed
    if not tags or not isinstance(tags, list) or len(tags) == 0:
        tags = [
            "shorts",
            "viral",
            "devotional",
            "hindu gods",
            "ai bhakti",
            "3d animation",
            "moral stories",
            "bhakti",
            "hindi story",
            "kids story",
        ]
        if character:
            tags.extend([character, character.lower(), f"{character.lower()} story"])
        if theme:
            tags.extend([theme, theme.lower()])

    # Ensure tags list contains both Hindi & English representations if missing
    tags = [str(t).strip() for t in tags if str(t).strip()][:15]

    return {
        "title": formatted_title,
        "description": description,
        "tags": tags,
    }


def generate_youtube_title(script_text, theme=None):
    return generate_youtube_metadata(script_text, theme=theme)["title"]


def generate_youtube_description(script_text, theme=None):
    return generate_youtube_metadata(script_text, theme=theme)["description"]


def generate_youtube_tags(script_text, theme=None):
    return generate_youtube_metadata(script_text, theme=theme)["tags"]
