import os

from aiogram import Bot
from aiogram.types import Audio, Sticker, PhotoSize, Message
from dotenv import load_dotenv
from groq import Groq
from groq.resources import Audio
from groq.types.chat import ChatCompletionMessageParam
from typing import cast
from datetime import date
from google import genai
import io
import mimetypes
import redis

load_dotenv()

GROQ_TOKEN = os.getenv("GROQ_TOKEN")
GENAI_TOKEN = os.getenv("GENAI_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")

client_groq = Groq(
    api_key=GROQ_TOKEN,
)
client_genai = genai.Client(
    api_key=GENAI_TOKEN,
)
client_redis = redis.Redis.from_url(REDIS_URL)

model_groq = "llama-3.1-8b-instant"
system = """Ты умеешь шутить и всегда это делаешь в контексте беседы. Ты токсичен очень сильно, обожаешь перепалки тут все свои. Тебя зову начальник или @antonlamma_bot но твое полное имя Вадим. Ты находишься в чате с @killmeluther - продюсер зовут Паша делает треки в составе группы lamma, @soldier21 - Никита репер под ником waltyboy немного странный, @augkgb - Ринат репер под ником aughost(август) семьянин взрослый самостоятельный человек.

Общаешься как обычный человек в групповом чате. Ты просто один из участников, не ведущий и не модератор. Не спрашивай кто на связи и не зазывай людей. Отвечай коротко и по делу, только если есть что сказать."""

models_genai = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def add_message(username: str, message: str):
    today = date.today().isoformat()

    keys = client_redis.keys("chat:*")
    for k in keys:
        if k.decode("utf-8") != f"chat:{today}":  # декодируем bytes
            client_redis.delete(k)

    client_redis.rpush(f"chat:{today}", f"{username}: {message}")
    client_redis.expire(f"chat:{today}", 86400)


def get_history() -> str:
    today = date.today().isoformat()
    messages = client_redis.lrange(f"chat:{today}", -5, -1)
    return "\n".join(m.decode("utf-8") for m in messages)


def generation_message_chat(history: str, text: str | None = None) -> str | None:
    if text:
        history = history + "\n" + text

    chat_history: list[ChatCompletionMessageParam] = [
        cast(ChatCompletionMessageParam, {
            "role": "system",
            "content": f"""
    {system}.
    История чата:
    """ + history
        }), cast(ChatCompletionMessageParam, {
            "role": "user",
            "content": "Ответь на последнее сообщение находят в контексте истории чата"
        })
    ]

    completion = client_groq.chat.completions.create(
        model=model_groq,
        messages=chat_history
    )

    return completion.choices[0].message.content


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


async def analyze_file(file: Audio | Sticker | PhotoSize, bot: Bot):
    buf = io.BytesIO()
    await bot.download(file.file_id, destination=buf)
    buf.seek(0)

    match file:
        case Audio():
            prompt = "Ты саунд продюсер с 10 летним стажем должен оценить аудиозапись которую тебе передали. Напиши так же удачную строчку которая тебе понравилась. Только коротко в пару предложений"
            file_name = file.file_name or f"{file.file_id}.mp3"
            mime_type = "audio/mpeg"
        case Sticker():
            prompt = "Что на этом стикере? Опиши в одно предложение, смешно с подколом"
            file_name = f"{file.file_id}.webp"
            mime_type = "image/webp"
        case PhotoSize():
            prompt = "Что на этой картинке? Опиши в одно предложение, смешно с подколом"
            file_name = f"{file.file_id}.jpg"
            mime_type = mimetypes.guess_type(file_name)[0] or "image/jpeg"

    for model in models_genai:
        try:
            uploaded = client_genai.files.upload(file=buf, config={"mime_type": mime_type, "display_name": file_name})
            response = client_genai.models.generate_content(
                model=model,
                contents=[prompt, uploaded]
            )
            add_message(f"FILE:{file_name}", response.text)
            return response.text
        except Exception:
            buf.seek(0)
            continue

    return "Друг соси)"


async def transcribe_voice(file_id: str, bot: Bot) -> tuple[str, str]:
    buf = io.BytesIO()
    await bot.download(file_id, destination=buf)
    buf.seek(0)
    history = get_history()

    transcription = client_groq.audio.transcriptions.create(
        file=("voice.ogg", buf),
        model="whisper-large-v3-turbo",
    )

    messages: list[ChatCompletionMessageParam] = [cast(ChatCompletionMessageParam, {
        "role": "system",
        "content": "Тебе надо вытащить из текста самое нужное, и кратко пересказать в пару пунктов"
    }), cast(ChatCompletionMessageParam, {
        "role": "user",
        "content": transcription.text
    })]

    completion = client_groq.chat.completions.create(
        model=model_groq,
        messages=messages
    )

    message_res = completion.choices[0].message.content

    today = date.today().isoformat()

    client_redis.rpush(f"voice:{today}", f"{message_res}")
    client_redis.expire(f"voice:{today}", 86400)

    return generation_message_chat(history, transcription.text), message_res


def generate_history_voices():
    today = date.today().isoformat()

    redis_messages = client_redis.lrange(f"chat:{today}", 0, -1)

    messages: list[ChatCompletionMessageParam] = [cast(ChatCompletionMessageParam, {
        "role": "system",
        "content": "Тебе надо из полученной информации разбить кратко по пунктам о чем говорилось"
    }), cast(ChatCompletionMessageParam, {
        "role": "user",
        "content": f"о чем говорили: {"\n".join(m.decode("utf-8") for m in redis_messages)}"
    })]

    completion = client_groq.chat.completions.create(
        model=model_groq,
        messages=messages
    )

    message_res = completion.choices[0].message.content

    return message_res


async def client_model_handler(message: Message, bot: Bot) -> str | None:
    add_message(message.from_user.username, message.text)
    history = get_history()

    if message == "/voices":
        return generate_history_voices()

    if message == "/refresh_history":
        client_redis.flushdb()

    if message == "/sound":
        return generation_message()

    if message == "/history":
        return history

    if "@antonlamma_bot" in message.text or (
            message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        return generation_message_chat(history)
    return None
