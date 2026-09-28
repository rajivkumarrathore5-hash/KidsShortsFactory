import json
import requests
from google import genai
from config import (
    get_secret,
    GEMINI_MODEL_CHAIN,
    GROQ_MODEL_CHAIN,
    OPENROUTER_MODEL_CHAIN,
    REMEMBER_LAST_MODEL,
)
from pipeline.pre_run_settings import load_config_state, CONFIG_STATE_PATH
from .history import generate_unique_script


def get_ordered_model_chain():
    """
    Builds the flat list of models across Gemini, Groq, and OpenRouter layers.
    If REMEMBER_LAST_MODEL is True, places the last successful model at index 0.
    """
    chain = []
    for m in GEMINI_MODEL_CHAIN:
        chain.append(("gemini", m))
    for m in GROQ_MODEL_CHAIN:
        chain.append(("groq", m))
    for m in OPENROUTER_MODEL_CHAIN:
        chain.append(("openrouter", m))

    last_model = None
    if REMEMBER_LAST_MODEL:
        state = load_config_state()
        last_model = state.get("last_successful_model", "").strip()

    print(f"[MODEL] Last successful: {last_model if last_model else 'None'}")

    if REMEMBER_LAST_MODEL and last_model:
        matching_idx = next((i for i, (p, m) in enumerate(chain) if m == last_model), -1)
        if matching_idx != -1:
            matched_item = chain.pop(matching_idx)
            chain.insert(0, matched_item)
            print(f"[MODEL] Starting with last successful: {last_model}")

    try_order_str = ", ".join(m for _, m in chain)
    print(f"[MODEL] Try order: {try_order_str}")

    return chain


def save_last_successful_model(model_name: str):
    """
    Persists the last successful model (or clears it on failure) in config_state.json.
    """
    if not REMEMBER_LAST_MODEL:
        return
    try:
        state = load_config_state()
        state["last_successful_model"] = model_name
        CONFIG_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
        if model_name:
            print(f"[MODEL] Saved as last successful: {model_name}")
        else:
            print("[MODEL] All models exhausted. Clearing last successful.")
    except Exception as e:
        print(f"[WARNING] Could not update last_successful_model in config_state.json: {e}")


def generate_text_with_fallback(prompt: str, is_metadata: bool = False) -> str:
    """
    Executes prompt generation across the ordered flat model chain.
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

    model_chain = get_ordered_model_chain()
    total_models = len(model_chain)

    for idx, (provider, model_name) in enumerate(model_chain, start=1):
        # 1. Gemini
        if provider == "gemini":
            if not gemini_client:
                print(f"[WARN] Gemini API key missing, skipping {model_name}...")
                continue
            print(f"[INFO] Trying Gemini model {idx}/{total_models}: {model_name}")
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text and response.text.strip():
                    save_last_successful_model(model_name)
                    print(f"[OK] {'Metadata' if is_metadata else 'Script'} generated with Gemini model: {model_name}")
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

        # 2. Groq
        elif provider == "groq":
            if not groq_client:
                print(f"[WARN] Groq API key missing or client unavailable, skipping {model_name}...")
                continue
            print(f"[INFO] Trying Groq model {idx}/{total_models}: {model_name}")
            try:
                completion = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name,
                )
                content = completion.choices[0].message.content
                if content and content.strip():
                    save_last_successful_model(model_name)
                    print(f"[OK] {'Metadata' if is_metadata else 'Script'} generated with Groq model: {model_name}")
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

        # 3. OpenRouter
        elif provider == "openrouter":
            if not openrouter_api_key:
                print(f"[WARN] OpenRouter API key missing, skipping {model_name}...")
                continue
            print(f"[INFO] Trying OpenRouter model {idx}/{total_models}: {model_name}")
            try:
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://kidsshortsfactory.local",
                    "X-Title": "KidsShortsFactory",
                }
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
                            save_last_successful_model(model_name)
                            print(f"[OK] {'Metadata' if is_metadata else 'Script'} generated with OpenRouter model: {model_name}")
                            return content
                err_text = res.text
                full_reason = f"HTTP {res.status_code} - {err_text}"
                if res.status_code in (402, 429) or "402" in err_text or "429" in err_text:
                    print(f"[FALLBACK] OpenRouter {model_name} quota/balance limit reached, trying next... Reason: {full_reason}")
                else:
                    print(f"[WARN] OpenRouter {model_name} failed, trying next... Reason: {full_reason}")
            except Exception as err:
                print(f"[WARN] OpenRouter {model_name} failed: {err}, trying next...")

    # If all models fail:
    save_last_successful_model("")
    if is_metadata:
        return ""
    raise RuntimeError("All Gemini, Groq, and OpenRouter models exhausted. Try again later.")


def generate_script(character=None, theme=None, duration=15, theme_config=None, scene_count=4, video_mode="short"):
    return generate_unique_script(
        generate_text_with_fallback,
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