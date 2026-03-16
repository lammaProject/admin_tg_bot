import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from huggingface_hub import InferenceClient

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_KEY")
HUGGING_TOKEN = os.getenv("HUGGING_TOKEN")

config = types.GenerateContentConfig(
    system_instruction=(
        'Ты репер, фанат 2Pac и OG Buda. Отвечаешь в чате как обычный живой человек — '
        'коротко, по делу, без пафоса. 1-3 предложения максимум. '
        'Никаких длинных монологов и списков. Пишешь как в личке с другом.'
    )
)

client = genai.Client(api_key=GEMINI_KEY)
image_client = InferenceClient(provider='hf-inference', api_key=HUGGING_TOKEN)


async def client_model_handler(message: str):
    retries = 0
    response = None
    model = 'gemini-2.5-flash'
    fallback_model = 'katanemo/Arch-Router-1.5B'

    while retries < 3:
        try:
            response = client.models.generate_content(model=model,
                                                      config=config,
                                                      contents=message)
        except Exception as e:
            retries += 1
            model = fallback_model

    if response is None:
        return ""

    return response.text
