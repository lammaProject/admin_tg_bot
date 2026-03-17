import os

from aiogram import Bot
from aiogram.types import Audio, Sticker
from dotenv import load_dotenv
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
from typing import cast
from datetime import date
from google import genai
import io

load_dotenv()

GROQ_TOKEN = os.getenv("GROQ_TOKEN")
GENAI_TOKEN = os.getenv("GENAI_TOKEN")

client_groq = Groq(
    api_key=GROQ_TOKEN,
)
client_genai = genai.Client(
    api_key=GENAI_TOKEN,
)

cache: dict[str, list[str]] = {}

model_groq = "llama-3.1-8b-instant"
system = """Ты умеешь шутить и всегда это делаешь в контексте беседы. Ты токсичен очень сильно, обожаешь перепалки тут все свои. Тебя зову начальник или @antonlamma_bot. Ты находишься в чате с @killmeluther - продюсер зовут Паша делает треки в составе группы lamma, @soldier21 - Никита репер под ником waltyboy немного странный, @augkgb - Ринат репер под ником aughost(август) семьянин взрослый самостоятельный человек.

Общаешься как обычный человек в групповом чате. Ты просто один из участников, не ведущий и не модератор. Не спрашивай кто на связи и не зазывай людей. Отвечай коротко и по делу, только если есть что сказать."""


def add_message(username: str, message: str):
    today = date.today().isoformat()

    old_keys = [k for k in cache if k != today]
    for k in old_keys:
        del cache[k]

    if today not in cache:
        cache[today] = []

    cache[today].append(f"{username}: {message}")


def parse_message(message_res: str) -> tuple[str, bool]:
    text = message_res.replace("isAnswer:true", "").replace("isAnswer:false", "").strip()
    return text, "isAnswer:true" in message_res


def generation_message_chat(username: str, message: str, history: str, default_answer: bool) -> str | None:
    chat_history: list[ChatCompletionMessageParam] = [
        cast(ChatCompletionMessageParam, {
            "role": "system",
            "content": f"""
    {system}.{not default_answer and "Если считаешь что нужно принять участие в дискуссии то отправляй в конце isAnswer:true иначе isAnswer:false"}
    История чата:
    """ + history
        }),
        cast(ChatCompletionMessageParam, {
            "role": "user",
            "content": f"{username}: {message}"
        })
    ]

    completion = client_groq.chat.completions.create(
        model=model_groq,
        messages=chat_history
    )

    message_res = completion.choices[0].message.content
    text, is_answer = parse_message(message_res)

    if is_answer or default_answer:
        return text

    else:
        return None


def generation_message():
    messages: list[ChatCompletionMessageParam] = [cast(ChatCompletionMessageParam, {
        "role": "system",
        "content": f"{system}"
    }), cast(ChatCompletionMessageParam, {
        "role": "user",
        "content": f"Назови какой нибудь факт как лучше всего сводить или писать музыку или сочинять"
    })]

    completion = client_groq.chat.completions.create(
        model=model_groq,
        messages=messages,
        temperature=0.9
    )

    message_res = completion.choices[0].message.content
    return message_res


async def analyze_file(file: Audio | Sticker, bot: Bot):
    buf = io.BytesIO()
    await bot.download(file.file_id, destination=buf)
    buf.seek(0)

    is_audio = isinstance(file, Audio)

    prompt = "Ты саунд продюсер с 10 летним стажем должен оценить аудиозапись которую тебе передали. Напиши так же удачную строчку которая тебе понравилась. Только коротко в пару предложений." if is_audio else "Что на этом стикере? Опиши в одно предложение, смешно с подколом"

    config = {"mime_type": "audio/mpeg", "display_name": file.file_name} if is_audio else {"mime_type": "image/webp"}

    file_name = file.file_name if is_audio else "sticker"

    uploaded = client_genai.files.upload(file=buf, config=config)

    response = client_genai.models.generate_content(
        model='gemini-3-flash-preview',
        contents=[prompt, uploaded]
    )

    add_message(f"FILE:{file_name}", response.text)

    return response.text


async def client_model_handler(message: str, username: str | None = None) -> str | None:
    add_message(username, message)
    history = "\n".join(cache.get(date.today().isoformat(), []))

    if message == "/sound":
        return generation_message()

    if message == "/history":
        return f"{username} запросил: {history}"

    if "@antonlamma_bot" in message:
        return generation_message_chat(username, message, history, True)

    return generation_message_chat(username, message, history, False)
