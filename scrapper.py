import asyncio
import os

from dotenv import load_dotenv
from release_parser import get_yesterday, fetch_yesterdays_releases, format_releases_message, split_telegram_message
from aiogram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


async def scrapper_test():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not CHAT_ID:
        raise RuntimeError("CHAT_ID is not set")

    bot = Bot(token=BOT_TOKEN)

    try:

        print('start')
        target_date = get_yesterday('Asia/Yekaterinburg')
        print(target_date)
        releases = fetch_yesterdays_releases(
        )
        total_count = len(releases)
        text = format_releases_message(releases, target_date, total_count=total_count)
        print(text)

        for message in split_telegram_message(text):
            await bot.send_message(CHAT_ID, message)


    finally:
        await bot.session.close()


asyncio.run(scrapper_test())
