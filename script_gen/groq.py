from groq import Groq
from config import get_secret
from .history import generate_unique_script


def _generate_response(client, prompt):
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="mixtral-8x7b-32768",
    )
    return chat_completion.choices[0].message.content


def generate_script(character=None, theme=None, duration=15, theme_config=None, scene_count=4):
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is blank in the project-root secrets.py file.")
    client = Groq(api_key=api_key)

    def generate_response(prompt):
        return _generate_response(client, prompt)

    return generate_unique_script(
        generate_response,
        character=character,
        theme=theme,
        duration=duration,
        theme_config=theme_config,
        scene_count=scene_count,
    )
