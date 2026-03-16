import os
import json
import random
import asyncio
import logging
from http.server import BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from llm import client_model_handler

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

reactions = [
    "👍", "👎", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢",
    "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡", "🥱", "🥴", "😍", "🐳",
    "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓",
    "🍾", "💋", "🖕", "😈", "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈",
    "😇", "😂", "🤝", "🤙",
]


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
        if not message.text:
            return
        if message.from_user and message.from_user.id == bot.id:
            return

        text = await client_model_handler(message.text, message.from_user.username)
        if not text:
            return
        await message.reply(text)
        await message.react([types.ReactionTypeEmoji(emoji=random.choice(reactions))])

    try:
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()
