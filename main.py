import logging
import os
import random
from datetime import datetime

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Application

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
POST_TIME = os.getenv("POST_TIME", "09:00")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

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

        # Ищем блоки с анекдотами (data-t="j" — тип "анекдот")
        joke_blocks = soup.find_all("div", class_="topicbox", attrs={"data-t": "j"})

        jokes = []
        for block in joke_blocks:
            text_div = block.find("div", class_="text")
            if text_div:
                # Заменяем <br> на перенос строки
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


async def post_anekdot(bot: Bot) -> None:
    """Получает анекдот и публикует его в канал."""
    logger.info(f"Публикация анекдота в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    joke = fetch_random_anekdot()
    if not joke:
        logger.error("Не удалось получить анекдот, публикация пропущена")
        return

    message = f"😄 *Анекдот дня*\n\n{joke}\n\n_© anekdot.ru_"

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode="Markdown",
        )
        logger.info("Анекдот успешно опубликован")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в канал: {e}")


async def send_test_message(bot: Bot) -> None:
    """Отправляет тестовое сообщение при старте бота."""
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text="test")
        logger.info("Тестовое сообщение отправлено")
    except Exception as e:
        logger.error(f"Ошибка при отправке тестового сообщения: {e}")


async def on_startup(app: Application) -> None:
    """Вызывается после старта бота — шлём test и запускаем планировщик."""
    # Парсим время публикации
    hour, minute = map(int, POST_TIME.split(":"))

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        post_anekdot,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
        args=[app.bot],
        name="daily_anekdot",
    )
    scheduler.start()

    logger.info(
        f"Бот запущен. Анекдот будет публиковаться каждый день в {POST_TIME} ({TIMEZONE})"
    )
    logger.info(f"Канал: {CHANNEL_ID}")

    # Тестовое сообщение при старте
    await send_test_message(app.bot)


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env файле")
    if not CHANNEL_ID:
        raise ValueError("CHANNEL_ID не задан в .env файле")

    try:
        map(int, POST_TIME.split(":"))
    except ValueError:
        raise ValueError(f"Неверный формат POST_TIME: '{POST_TIME}', ожидается HH:MM")

    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    # Запускаем бота (idle — ждём остановки)
    app.run_polling(allowed_updates=[])


if __name__ == "__main__":
    main()
