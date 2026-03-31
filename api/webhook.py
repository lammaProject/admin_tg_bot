import os
import json
import random
import asyncio
import logging
import httpx
from http.server import BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from llm import client_model_handler, analyze_file

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
NAME_BOT = os.getenv("NAME_BOT")
NICK_BOT = os.getenv("NICK_BOT")
BOT2_WEBHOOK_URL = os.getenv("BOT2_WEBHOOK_URL")
OTHER_BOTS = json.loads(os.getenv("OTHER_BOTS", "[]"))

reactions = [
    "👍", "👎", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢",
    "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡", "🥱", "🥴", "😍", "🐳",
    "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓",
    "🍾", "💋", "🖕", "😈", "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈",
    "😇", "😂", "🤝", "🤙",
]


async def ping_bot2(text: str, chat_id: int):
    if not BOT2_WEBHOOK_URL:
        logger.info("BOT2_WEBHOOK_URL не задан")
        return

    logger.info(f"Пингую бота: {BOT2_WEBHOOK_URL} с текстом: {text!r}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BOT2_WEBHOOK_URL}/api/webhook",
            json={...}
        )
        logger.info(f"Ответ: {response.status_code} {response.text}")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            update_data = json.loads(body.decode("utf-8"))
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(process_update(update_data))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error processing update: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


async def process_update(update_data: dict):
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    @dp.message()
    async def message_handler(message: types.Message):
        if message.from_user and message.from_user.id == bot.id:
            return

        is_bot_ping = message.text and message.text.startswith("[BOT_PING]")
        text = (message.text or "").replace("[BOT_PING] ", "")

        mentioned = (
                NAME_BOT.lower() in text.lower() or
                NICK_BOT.lower() in text.lower() or
                (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
        )

        if mentioned:
            if message.photo:
                result = await analyze_file(message.photo[-1], bot)
                await bot.send_message(message.chat.id, result)
            if message.sticker:
                result = await analyze_file(message.sticker, bot)
                await bot.send_message(message.chat.id, result)
            if message.audio:
                result = await analyze_file(message.audio, bot)
                await bot.send_message(message.chat.id, result)

        if not text:
            return

        response = await client_model_handler(message, bot)
        if not response:
            return

        if is_bot_ping:
            await bot.send_message(message.chat.id, response)  # не reply на фейковый апдейт
        else:
            await message.reply(response)
            await message.react([types.ReactionTypeEmoji(emoji=random.choice(reactions))])

        if not is_bot_ping and any(
                part in response
                for p in OTHER_BOTS
                for part in p.get("имя", "").split()
                if part not in (NAME_BOT, NICK_BOT)  # исключаем себя
        ):
            await ping_bot2(response, message.chat.id)

    try:
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()
