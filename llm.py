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


def parse_message(message_res: str) -> tuple[str, bool]:
    text = message_res.replace("isAnswer:true", "").replace("isAnswer:false", "").strip()
    return text, "isAnswer:true" in message_res


async def client_model_handler(message: str, username: str | None = None) -> str | None:
    add_message(username, message)
    history = "".join(cache.get(date.today().isoformat(), []))

    if message == "/history":
        return f"${username} запросил: ${history}"

    chat_history: list[ChatCompletionMessageParam] = [cast(ChatCompletionMessageParam, {
        "role": "system",
        "content": "Ты саунд продюсер помощник тебя зовут Начальник или @antonlamma_bot, ты разбираешься в ключевых вещах связанных с музыкой, знаешь как правильно сводить и делать ее. Ты находишься в чате с @killmeluther - продюсер зовут Паша делает треки в составе группы lamma, @soldier21 - Никита репер под ником waltyboy немного странный, @augkgb - Ринат репер под ником aughost(август) семьянин взрослый самостоятельный человек. Если считаешь что нужно принять участие в дискуссии то отправляй в конце isAnswer:true иначе isAnswer:false"
    }), {"role": "user", "content": history + f"${username}${message}"}]

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=chat_history
    )

    message_res = completion.choices[0].message.content
    text, isAnswer = parse_message(message_res)

    if isAnswer:
        return text

    else:
        return None
