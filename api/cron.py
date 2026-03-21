import asyncio
import os
from http.server import BaseHTTPRequestHandler

from aiogram import Bot

from llm import generation_message_chat

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(process())
        finally:
            loop.close()

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


async def process():
    bot = Bot(token=BOT_TOKEN)

    text = generation_message_chat("Отправь кому нибудь из чата сообщение, узнай почему молчание в чате, и тегни его")

    await bot.send_message(CHAT_ID, text)

    await bot.session.close()
