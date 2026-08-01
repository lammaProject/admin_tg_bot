import asyncio
import os
from http.server import BaseHTTPRequestHandler

from aiogram import Bot
from dotenv import load_dotenv

from release_parser import (
    DEFAULT_TIMEZONE,
    DEFAULT_YANDEX_MUSIC_EXTRA_SEARCH_QUERIES,
    ReleaseParserError,
    fetch_yesterdays_releases,
    format_releases_message,
    get_yesterday,
    split_telegram_message,
)
from scrapper import scrapper_test

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RELEASES_TIMEZONE = os.getenv("RELEASES_TIMEZONE", DEFAULT_TIMEZONE)
RELEASES_SOURCE = os.getenv("RELEASES_SOURCE", "yandex_music")
RELEASES_FETCH_ATTEMPTS = int(os.getenv("RELEASES_FETCH_ATTEMPTS", "3"))
RELEASES_RETRY_DELAY = float(os.getenv("RELEASES_RETRY_DELAY", "2"))
RELEASES_FALLBACK_TO_HTML = os.getenv("RELEASES_FALLBACK_TO_HTML", "0").lower() in {"1", "true", "yes", "on"}
RELEASES_LIMIT = int(os.getenv("RELEASES_LIMIT", "10"))
RELEASES_EXTRA_SEARCH_QUERIES = tuple(
    query.strip()
    for query in
    os.getenv("RELEASES_EXTRA_SEARCH_QUERIES", ";".join(DEFAULT_YANDEX_MUSIC_EXTRA_SEARCH_QUERIES)).split(";")
    if query.strip()
)
YANDEX_MUSIC_TOKEN = os.getenv("YANDEX_MUSIC_TOKEN")


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
    await scrapper_test()
