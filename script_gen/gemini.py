import requests
from google import genai
from config import get_secret, GEMINI_MODEL_CHAIN, GROQ_MODEL_CHAIN, OPENROUTER_MODEL_CHAIN
from .history import generate_unique_script


def generate_script(character=None, theme=None, duration=15, theme_config=None, scene_count=4, video_mode="short"):
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

    def generate_response(prompt):
        # LAYER 1: Gemini fallback chain
        if gemini_client:
            total_gemini = len(GEMINI_MODEL_CHAIN)
            for idx, model_name in enumerate(GEMINI_MODEL_CHAIN, start=1):
                print(f"[INFO] Trying Gemini model {idx}/{total_gemini}: {model_name}")
                try:
                    response = gemini_client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    if response and response.text:
                        print(f"[OK] Script generated with Gemini model: {model_name}")
                        return response.text
                except Exception as err:
                    err_str = str(err)
                    is_429 = (
                        "429" in err_str
                        or "RESOURCE_EXHAUSTED" in err_str
                        or "quota" in err_str.lower()
                    )
                    if is_429:
                        print(f"[FALLBACK] Gemini {model_name} quota exceeded (429), trying next... Reason: {err_str}")
                    else:
                        print(f"[WARN] Gemini {model_name} failed: {err_str}, trying next...")

        # LAYER 2: Groq fallback chain
        print("[FALLBACK] All Gemini models exhausted, switching to Groq...")
        total_groq = len(GROQ_MODEL_CHAIN)
        print(f"[INFO] Switching to Groq fallback chain ({total_groq} models)")

        if groq_client:
            for idx, model_name in enumerate(GROQ_MODEL_CHAIN, start=1):
                print(f"[INFO] Trying Groq model {idx}/{total_groq}: {model_name}")
                try:
                    completion = groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name,
                    )
                    content = completion.choices[0].message.content
                    if content and content.strip():
                        print(f"[OK] Script generated with Groq model: {model_name}")
                        return content
                except Exception as err:
                    err_str = str(err)
                    is_404 = (
                        "404" in err_str
                        or "model_not_found" in err_str.lower()
                        or "not found" in err_str.lower()
                    )
                    if is_404:
                        print(f"[FALLBACK] Groq {model_name} model not found (404), skipping immediately... Reason: {err_str}")
                    else:
                        print(f"[FALLBACK] Groq {model_name} failed, trying next... Reason: {err_str}")
        else:
            if not groq_api_key:
                print("[WARN] Groq API key is missing.")

        # LAYER 3: OpenRouter Free Models fallback chain
        print("[FALLBACK] Gemini and Groq exhausted, switching to OpenRouter free models...")
        total_openrouter = len(OPENROUTER_MODEL_CHAIN)
        print(f"[INFO] Switching to OpenRouter fallback chain ({total_openrouter} models)")

        if openrouter_api_key:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://kidsshortsfactory.local",
                "X-Title": "KidsShortsFactory",
            }
            for idx, model_name in enumerate(OPENROUTER_MODEL_CHAIN, start=1):
                print(f"[INFO] Trying OpenRouter model {idx}/{total_openrouter}: {model_name}")
                try:
                    payload = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                    res = requests.post(url, headers=headers, json=payload, timeout=45)
                    if res.status_code == 200:
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content", "")
                            if content and content.strip():
                                print(f"[OK] Script generated with OpenRouter model: {model_name}")
                                return content
                    err_text = res.text
                    full_reason = f"HTTP {res.status_code} - {err_text}"
                    if res.status_code in (402, 429) or "402" in err_text or "429" in err_text:
                        print(f"[FALLBACK] OpenRouter {model_name} quota/balance limit reached, trying next... Reason: {full_reason}")
                    else:
                        print(f"[WARN] OpenRouter {model_name} failed, trying next... Reason: {full_reason}")
                except Exception as err:
                    print(f"[WARN] OpenRouter {model_name} failed: {err}, trying next...")
        else:
            print("[WARN] OpenRouter API key is missing in secrets.py.")

        raise RuntimeError("All Gemini, Groq, and OpenRouter models exhausted. Try again later.")

    return generate_unique_script(
        generate_response,
        character=character,
        theme=theme,
        duration=duration,
        theme_config=theme_config,
        scene_count=scene_count,
        video_mode=video_mode,
    )


def generate_youtube_title(script_text, theme=None):
    from uploaders.metadata import generate_youtube_title as gen_title
    return gen_title(script_text, theme=theme)


def generate_youtube_description(script_text, theme=None):
    from uploaders.metadata import generate_youtube_description as gen_desc
    return gen_desc(script_text, theme=theme)


def generate_youtube_tags(script_text, theme=None):
    from uploaders.metadata import generate_youtube_tags as gen_tags
    return gen_tags(script_text, theme=theme)