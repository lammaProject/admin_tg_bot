import logging
import os
import asyncio
import random
import pytz

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from llm import generate_post, client_model_handler

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Moscow"))

reactions = ["👍", "👎", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡", "🥱",
             "🥴", "😍", "🐳", "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈", "😴", "😭",
             "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😂", "🤝", "🤙"]


@dp.message()
async def message_handler(message: types.Message):
    if not message.text:
        return
    if message.from_user.id == bot.id:
        return
    text = await client_model_handler(message.text)
    await message.reply(text)
    await message.react([types.ReactionTypeEmoji(emoji=random.choice(reactions))])


@scheduler.scheduled_job('cron', hour=8, minute=00)
async def scheduled_job():
    image, text = await generate_post()
    await bot.send_media_group(CHANNEL_ID, media=[
        types.InputMediaPhoto(media=types.BufferedInputFile(image, filename='image.png'), caption=text)])


async def main():
    scheduler.start()
    async with bot:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
