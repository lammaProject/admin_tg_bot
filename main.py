import asyncio
import logging
import os
import random

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

ANEKDOT_URL = "https://www.anekdot.ru/random/anekdot/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def fetch_random_anekdot() -> str | None:
    """Парсит случайный анекдот с anekdot.ru."""
    try:
        response = requests.get(ANEKDOT_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")

        joke_blocks = soup.find_all("div", class_="topicbox", attrs={"data-t": "j"})

        jokes = []
        for block in joke_blocks:
            text_div = block.find("div", class_="text")
            if text_div:
                for br in text_div.find_all("br"):
                    br.replace_with("\n")
                text = text_div.get_text(separator="").strip()
                if text:
                    jokes.append(text)

        if not jokes:
            logger.warning("Анекдоты не найдены на странице")
            return None

        return random.choice(jokes)

    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к anekdot.ru: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при парсинге: {e}")
        return None


async def send_anekdot() -> None:
    """Получает анекдот и отправляет в канал."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан")
    if not CHANNEL_ID:
        raise ValueError("CHANNEL_ID не задан")

    joke = fetch_random_anekdot()
    if not joke:
        raise RuntimeError("Не удалось получить анекдот")

    message = f"😄 *Анекдот дня*\n\n{joke}\n\n_© anekdot.ru_"

    bot = Bot(token=BOT_TOKEN)
    async with bot:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode="Markdown",
        )
    logger.info("Анекдот успешно опубликован")


if __name__ == "__main__":
    asyncio.run(send_anekdot())
