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
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            BOT2_WEBHOOK_URL,
            json={
                "update_id": 999,
                "message": {
                    "message_id": 1,
                    "from": {"id": 1, "is_bot": False, "first_name": NAME_BOT},
                    "chat": {"id": chat_id, "type": "supergroup"},
                    "date": 0,
                    "text": text
                }
            }
        )


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
        logger.info(f"text: {message.text!r}, entities: {message.entities}")
        if NAME_BOT in message.text or NICK_BOT in message.text or (
                message.reply_to_message and message.reply_to_message.from_user.id == bot.id):
            if message.photo:
                file = message.photo[-1]
                text = await analyze_file(file, bot)
                await message.reply(text)
            if message.sticker:
                text = await analyze_file(message.sticker, bot)
                await message.reply(text)
            if message.audio:
                text = await analyze_file(message.audio, bot)
                await message.reply(text)

        if not message.text:
            return
        if message.from_user and message.from_user.id == bot.id:
            return

        text = await client_model_handler(message, bot)
        if not text or text is None:
            return

        await message.reply(text)
        await message.react([types.ReactionTypeEmoji(emoji=random.choice(reactions))])

        if any(p.get("имя", "") in message.text for p in OTHER_BOTS):
            await ping_bot2(text, message.chat.id)

    try:
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()
