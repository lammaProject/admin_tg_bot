import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from release_parser import get_yesterday, fetch_yesterdays_releases, format_releases_message, split_telegram_message
from aiogram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def is_friday():
    return datetime.now().weekday() == 4


async def scrapper_test():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not CHAT_ID:
        raise RuntimeError("CHAT_ID is not set")

    if not is_friday():
        return

    bot = Bot(token=BOT_TOKEN)

    try:
        text = fetch_yesterdays_releases(
        )
        await bot.send_message(CHAT_ID, text)


    finally:
        await bot.session.close()


asyncio.run(scrapper_test())
