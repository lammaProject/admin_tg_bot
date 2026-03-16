"""
Скрипт для регистрации webhook у Telegram.
Запусти один раз после деплоя: python main.py
"""
import os
import asyncio
import logging

from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
VERCEL_URL: str = os.getenv("VERCEL_URL", "")


async def set_webhook():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set")
    if not VERCEL_URL:
        raise ValueError("VERCEL_URL is not set (e.g. https://your-project.vercel.app)")

    webhook_url = f"{VERCEL_URL}/api/webhook"
    bot = Bot(token=BOT_TOKEN)

    await bot.set_webhook(webhook_url)
    info = await bot.get_webhook_info()
    logger.info(f"Webhook set: {info.url}")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(set_webhook())
