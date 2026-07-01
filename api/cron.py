import asyncio
import os
from http.server import BaseHTTPRequestHandler

from aiogram import Bot

from release_parser import (
    DEFAULT_TIMEZONE,
    ReleaseParserError,
    fetch_yesterdays_releases,
    format_releases_message,
    get_yesterday,
    split_telegram_message,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RELEASES_TIMEZONE = os.getenv("RELEASES_TIMEZONE", DEFAULT_TIMEZONE)
RELEASES_FETCH_ATTEMPTS = int(os.getenv("RELEASES_FETCH_ATTEMPTS", "3"))
RELEASES_RETRY_DELAY = float(os.getenv("RELEASES_RETRY_DELAY", "2"))


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
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not CHAT_ID:
        raise RuntimeError("CHAT_ID is not set")

    bot = Bot(token=BOT_TOKEN)

    try:
        target_date = get_yesterday(RELEASES_TIMEZONE)
        try:
            releases = fetch_yesterdays_releases(
                timezone=RELEASES_TIMEZONE,
                attempts=RELEASES_FETCH_ATTEMPTS,
                retry_delay=RELEASES_RETRY_DELAY,
            )
            text = format_releases_message(releases, target_date)
        except ReleaseParserError as error:
            text = f"Не получилось получить релизы за {target_date:%d.%m.%Y}: {error}"

        for message in split_telegram_message(text):
            await bot.send_message(CHAT_ID, message)
    finally:
        await bot.session.close()
