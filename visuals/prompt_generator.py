from google import genai
from config import get_secret

def generate_prompt_from_script(script):
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is blank in the project-root secrets.py file.")
    client = genai.Client(api_key=api_key)

    prompt = f"""
    Given this kids' dialogue script:
    "{script}"
    
    Generate a detailed image generation prompt for a cartoon/animated style image.
    The image should be colorful, playful, and match the mood of the dialogue.
    Output only the prompt, no extra text.
    """
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )
    return response.text.strip()