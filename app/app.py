import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from .bot.config import Settings
from .bot.logging_setup import setup_logging
from .bot.routers import start, access, payments, chat_member
from .bot.db.init_db import init_db
from .bot.jobs.scheduler import start_background_jobs


async def main() -> None:
    setup_logging()
    settings = Settings()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown"),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp["settings"] = settings

    dp.include_router(start.router)
    dp.include_router(access.router)
    dp.include_router(payments.router)
    dp.include_router(chat_member.router)

    await init_db(settings)
    start_background_jobs(dp, bot, settings)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())