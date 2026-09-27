import json
import random
import re
import requests
from google import genai
from config import get_secret, GEMINI_MODEL_CHAIN, GROQ_MODEL_CHAIN, OPENROUTER_MODEL_CHAIN


def _llm_generate_text(prompt: str) -> str:
    """
    Generate text using the 3-layer fallback chain (Gemini -> Groq -> OpenRouter).
    """
    gemini_api_key = get_secret("GEMINI_API_KEY")
    groq_api_key = get_secret("GROQ_API_KEY")
    openrouter_api_key = get_secret("OPENROUTER_API_KEY")

    gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

    groq_client = None
    if groq_api_key:
        try:
            from groq import Groq
            groq_client = Groq(api_key=groq_api_key)
        except Exception:
            groq_client = None

    # LAYER 1: Gemini fallback chain
    if gemini_client:
        total_gemini = len(GEMINI_MODEL_CHAIN)
        for idx, model_name in enumerate(GEMINI_MODEL_CHAIN, start=1):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    return response.text
            except Exception as err:
                err_str = str(err)
                is_429 = (
                    "429" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "quota" in err_str.lower()
                )
                if is_429:
                    print(f"[FALLBACK] Gemini {model_name} quota exceeded (429) for metadata, trying next...")
                else:
                    print(f"[WARN] Gemini {model_name} failed for metadata: {err_str}, trying next...")

    # LAYER 2: Groq fallback chain
    if groq_client:
        total_groq = len(GROQ_MODEL_CHAIN)
        for idx, model_name in enumerate(GROQ_MODEL_CHAIN, start=1):
            try:
                completion = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name,
                )
                content = completion.choices[0].message.content
                if content and content.strip():
                    return content
            except Exception as err:
                print(f"[FALLBACK] Groq {model_name} failed for metadata: {err}")

    # LAYER 3: OpenRouter Free Models fallback chain
    if openrouter_api_key:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kidsshortsfactory.local",
            "X-Title": "KidsShortsFactory",
        }
        total_openrouter = len(OPENROUTER_MODEL_CHAIN)
        for idx, model_name in enumerate(OPENROUTER_MODEL_CHAIN, start=1):
            try:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                }
                res = requests.post(url, headers=headers, json=payload, timeout=45)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    if content and content.strip():
                        return content
            except Exception as err:
                print(f"[FALLBACK] OpenRouter {model_name} failed for metadata: {err}")

    return ""


def pick_random_title_language() -> str:
    """
    FIX 5: Randomly pick title language ('hindi', 'english', 'hinglish').
    """
    chosen = random.choice(["hindi", "english", "hinglish"])
    print(f"[META] Title language: {chosen}")
    return chosen


def validate_and_format_title(raw_title: str, character: str = None) -> str:
    """
    FIX 4: Validate and format title to be strictly <= 100 chars, ensuring #shorts is present.
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
    """
    chosen_lang = title_language or pick_random_title_language()
    theme_str = theme or "Devotion & Moral"
    char_str = character or "Indian Mythology"

    lang_instructions = {
        "hindi": (
            "Write Title & Description in Hindi (Devanagari script). "
            "Example Title: 'छोटे कृष्ण की माखन चोरी! 🧈 #shorts #viral #krishna #bhakti'. "
            "Call-To-Action: '🙏 दैनिक भक्ति और नैतिक कहानियों के लिए सब्सक्राइब करें!'"
        ),
        "english": (
            "Write Title & Description in English. "
            "Example Title: 'Little Krishna's Butter Stealing Tale! 🧈 #shorts #viral #krishna #bhakti'. "
            "Call-To-Action: '🙏 Subscribe for daily bhakti & moral stories!'"
        ),
        "hinglish": (
            "Write Title & Description in Hinglish (Roman script Hindi). "
            "Example Title: 'Chote Krishna ki Makhan Chori! 🧈 #shorts #viral #krishna #bhakti'. "
            "Call-To-Action: '🙏 Daily bhakti & moral stories ke liye subscribe karein!'"
        ),
    }
    selected_lang_rule = lang_instructions.get(chosen_lang, lang_instructions["hinglish"])

    mode_rule = ""
    if video_mode == "story":
        mode_rule = (
            "VIDEO MODE IS 'STORY':\n"
            "- Title MUST feature the suspenseful story hook / question (e.g. 'Krishna ne Govardhan Parvat Kaise Uthaya? 🏔️ #shorts #viral #krishna').\n"
            "- Description MUST explicitly highlight the moral/spiritual lesson of the story in 2-3 lines before hashtags.\n"
            "- Tags MUST include story narrative keywords (e.g. story, kahani, moral story, spiritual lesson).\n"
        )

    prompt = f"""
You are an expert YouTube Shorts creator for kids devotional and moral stories.
Generate YouTube Shorts metadata based on the following script:

Script:
{script_text}

Theme: {theme_str}
Character: {char_str}
Video Mode: {video_mode.upper()}
Target Language: {chosen_lang.upper()}

LANGUAGE RULES:
{selected_lang_rule}

{mode_rule}
1. YOUTUBE TITLE RULES:
- MUST be within 95 characters total.
- Structure: [Hook/Question] + [Character/Theme] + [1-2 Emojis] + [Hashtags]
- Required hashtags: ALWAYS include #shorts and #viral, plus 1-2 theme-specific hashtags (e.g., #krishna, #hanuman, #shiv, #ganesh, #jagannath, #durga, #lakshmi, #ram, #radha)
- Emojis: Include 1-2 relevant emojis (🙏, 🕉️, 🦚, 🪔, 🐒, 🐘, 🧈, 🏔️, etc.)

2. YOUTUBE DESCRIPTION RULES:
- Engaging summary of the video story and its moral lesson in {chosen_lang.upper()}.
- Include a clear call-to-action: "Subscribe for daily bhakti & moral stories!" (or target language equivalent).
- Include 5-10 hashtags at the END of the description:
  Always: #shorts #viral #bhakti
  Theme-specific: e.g. #krishna #radha #hanuman #shiv #ganesh #durga #lakshmi #ram
  Extra: #devotional #hindugods #aibhakti #3dart #moralstories #story

3. YOUTUBE TAGS RULES:
- Return 10-15 tags as a JSON array of string tags.
- Include BOTH Hindi (Devanagari script) and English/Hinglish versions (e.g. ["कृष्ण", "krishna", "हनुमान", "hanuman", "भक्ति", "bhakti", "shorts", "viral", "devotional", "hindu gods", "ai bhakti", "3d animation", "moral stories"]).
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
        elif chosen_lang == "english":
            title = f"✨ Divine Tale of Little {keyword} 🧈 #shorts #viral #{char_tag} #bhakti"
        else:
            title = f"✨ Chote {keyword} Ki Kahani 🧈 #shorts #viral #{char_tag} #bhakti"

    # FIX 4: Validate and format title length
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
