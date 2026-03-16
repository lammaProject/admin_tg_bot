import json
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

client_genai = genai.Client(api_key=GEMINI_KEY)
client_hugging = InferenceClient(provider="hf-inference", api_key=HUGGING_TOKEN, model="katanemo/Arch-Router-1.5B")
model = 'gemini-2.5-flash'


async def client_model_handler(message: str):
    try:
        res = await client_genai.models.generate_content(model=model,
                                                         config=config,
                                                         contents=message)
        return res.text
    except Exception as e:
        try:
            res = client_hugging.text_generation(prompt=config.system_instruction + message)
            parsed = json.loads(res)
            route = parsed["route"]
            print(route)
            print("test")
            return route
        except Exception as e:
            print(e)
