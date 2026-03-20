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

model_groq = "llama-3.3-70b-versatile"

models_genai = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

chats_peoples = [{"имя": "Ринат @augkgb"},
                 {"имя": "Никита @soldier21"},
                 {"имя": "Паша  @killmeluther"}, {"имя": "Антон @анонимный"}]

chats_peoples_text = "\n".join([f"{p['имя']}" for p in chats_peoples])

system = f"Запомни этих людей {chats_peoples_text}, отвечай смешно, тебя зовут Начальник ты токсичен и агрессивен. Ты в контексте чата, отвечай на последнее сообщение. Отвечай как человек небольшими предложениями словно ты в чате на твиче. ты внутри чата не надо писать словно ты чат."


def add_message(username: str, message: str):
    today = date.today().isoformat()

    keys = client_redis.keys("chat:*")
    for k in keys:
        if k.decode("utf-8") != f"chat:{today}":  # декодируем bytes
            client_redis.delete(k)

    client_redis.rpush(f"chat:{today}", f"{username}: {message}")
    client_redis.expire(f"chat:{today}", 86400)


def get_history() -> list[dict[str, str]]:
    today = date.today().isoformat()
    messages = client_redis.lrange(f"chat:{today}", -5, -1)
    result = [
        {"role": "user", "content": item.decode("utf-8")} for item in messages
    ]
    return result


def generation_message_chat(history: list[dict[str, str]], text: str | None = None) -> str | None:
    if text:
        history.append({"role": "user", "content": text})

    chat_history: list[ChatCompletionMessageParam] = [
        cast(ChatCompletionMessageParam, {
            "role": "system",
            "content": f"{system}"
        }), *history
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
            images_scan = client_redis.lrange("images", 0, -1)
            people_images = []

            if not images_scan:
                for i in range(2):
                    file_people = f"./images/people{i}.png"
                    people_image = client_genai.files.upload(file=file_people,
                                                             config={"mime_type": mime_type,
                                                                     "display_name": "people_image.png"})
                    client_redis.rpush(f"images", people_image.name)
                    client_redis.expire(f"images", 108000)
                    people_images.append(people_image)
            else:
                for item in images_scan:
                    people_images.append(item)

            uploaded = client_genai.files.upload(file=buf, config={"mime_type": mime_type, "display_name": file_name})

            response = client_genai.models.generate_content(
                model=model,
                contents=[
                    "Это как выглядит Антон из чата просто запомни:",
                    people_images[0],
                    # "Это как выглядит Никита из чата просто запомни:",
                    # people_images[1],
                    # "Это как выглядит Ринат из чата просто запомни:",
                    # people_images[2],
                    "Это фото которое нужно проанализировать и сравнить с людьми выше (если люди выше есть на этом фото):",
                    uploaded,
                    f"{prompt} {chats_peoples_text}"
                ]
            )

            return response.text
        except Exception:
            buf.seek(0)
            return Exception
            continue

    return "Друг соси)"


# async def transcribe_voice(file_id: str, bot: Bot) -> tuple[str, str]:
#     buf = io.BytesIO()
#     await bot.download(file_id, destination=buf)
#     buf.seek(0)
#     history = get_history()
#
#     transcription = client_groq.audio.transcriptions.create(
#         file=("voice.ogg", buf),
#         model="whisper-large-v3-turbo",
#     )
#
#     messages: list[ChatCompletionMessageParam] = [cast(ChatCompletionMessageParam, {
#         "role": "system",
#         "content": f"{system} Тебе надо вытащить из текста самое нужное, и кратко пересказать в пару пунктов, не надо отвечать, только краткий пересказ"
#     }), cast(ChatCompletionMessageParam, {
#         "role": "user",
#         "content": transcription.text
#     })]
#
#     completion = client_groq.chat.completions.create(
#         model=model_groq,
#         messages=messages
#     )
#
#     message_res = completion.choices[0].message.content
#
#     today = date.today().isoformat()
#
#     client_redis.rpush(f"voice:{today}", f"{message_res}")
#     client_redis.expire(f"voice:{today}", 86400)
#
#     return generation_message_chat(history, transcription.text), message_res


async def client_model_handler(message: Message, bot: Bot) -> str | None:
    add_message(message.from_user.username, message.text)
    history = get_history()

    if message.text == "/refresh_history":
        client_redis.flushdb()

    if message.text == "/sound":
        return generation_message()

    if "@antonlamma_bot" in message.text or (
            message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
        return generation_message_chat(history)
    return None
