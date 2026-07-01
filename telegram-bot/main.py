import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database.db import init_db
from handlers import start, games, payments, admin, partner, support
from handlers import franchise as franchise_handler
import franchise_runner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Exposed so franchise.py can reference it without circular imports
dp: Dispatcher | None = None


async def main():
    global dp
    await init_db()
    logger.info("Database initialized")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Share dispatcher reference with franchise_runner (avoids circular imports)
    franchise_runner.MAIN_DP = dp

    # Register routers — franchise payment filter must be before payments router
    dp.include_router(franchise_handler.router)
    dp.include_router(support.router)
    dp.include_router(partner.router)
    dp.include_router(admin.router)
    dp.include_router(payments.router)
    dp.include_router(games.router)
    dp.include_router(start.router)

    # Start all active franchise bots
    await franchise_runner.load_all_franchise_bots(dp)

    logger.info("Starting bot polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
