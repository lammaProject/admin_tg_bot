import os

from dotenv import load_dotenv
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
from typing import cast
from datetime import date

load_dotenv()

GROQ_TOKEN = os.getenv("GROQ_TOKEN")

client = Groq(
    api_key=GROQ_TOKEN,
)

cache: dict[str, list[str]] = {}


def add_message(username: str, message: str):
    today = date.today().isoformat()

    old_keys = [k for k in cache if k != today]
    for k in old_keys:
        del cache[k]

    if today not in cache:
        cache[today] = []

    cache[today].append(f"{username}: {message}")


async def client_model_handler(message: str, username: str | None = None):
    add_message(username, message)
    history = "".join(cache.get(date.today().isoformat(), []))

    if message == "/history":
        return f"${username} запросил: ${history}"

    chat_history: list[ChatCompletionMessageParam] = [cast(ChatCompletionMessageParam, {
        "role": "system",
        "content": "Ты саунд продюсер помощник тебя зовут Начальник или @antonlamma_bot, ты разбираешься в ключевых вещах связанных с музыкой, знаешь как правильно сводить и делать ее. Ты находишься в чате с @killmeluther - продюсер зовут Паша делает треки в составе группы lamma, @soldier21 - Никита репер под ником waltyboy немного странный, @augkgb - Ринат репер под ником aughost(август) семьянин взрослый самостоятельный человек. Отвечай только на сообщения в которых считаешь нужным принять участие и возвращай в конце сообщения isAnswer"
    }), {"role": "user", "content": history + f"${username}${message}"}]

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=chat_history
    )

    return completion.choices[0].message.content
