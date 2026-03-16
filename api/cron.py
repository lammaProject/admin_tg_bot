import os
import asyncio
import logging
from http.server import BaseHTTPRequestHandler

from aiogram import Bot, types
from dotenv import load_dotenv
from llm import generate_post

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")


async def post_to_channel():
    bot = Bot(token=BOT_TOKEN)
    try:
        image, text = await generate_post()
        await bot.send_media_group(
            CHANNEL_ID,
            media=[
                types.InputMediaPhoto(
                    media=types.BufferedInputFile(image, filename="image.png"),
                    caption=text,
                )
            ],
        )
        logger.info("Post sent successfully")
    finally:
        await bot.session.close()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            asyncio.run(post_to_channel())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Post sent")
        except Exception as e:
            logger.error(f"Cron error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())
