import os

from io import BytesIO
from typing import Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types
from huggingface_hub import InferenceClient

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_KEY")
HUGGING_TOKEN = os.getenv("HUGGING_TOKEN")

config = types.GenerateContentConfig(
    system_instruction='Ты крутой репер, обожаешь 2Pac, OG Buda и прочих реперов, ты true OG бро!'
)
model = 'gemini-2.5-flash'

client = genai.Client(api_key=GEMINI_KEY)
image_client = InferenceClient(provider='hf-inference', api_key=HUGGING_TOKEN)


async def client_model_handler(message: str):
    response = client.models.generate_content(model=model, config=config, contents=message)
    return response.text


async def generate_post() -> Tuple[bytes, str]:
    text = await client_model_handler(
        'Придумай интересный пост, он может быть связан с чем угодно и о чем угодно из жизни репера! Не больше 1024 символов. В конце поста напиши image:(тут опиши промт для картинки связанную с ним)')

    parts = text.split("image:")

    post_text = parts[0].strip()
    image_prompt = parts[1].strip() if len(parts) > 1 else ""

    image = image_client.text_to_image(
        image_prompt,
        model="black-forest-labs/FLUX.1-schnell",
    )
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)

    return buf.read(), post_text
