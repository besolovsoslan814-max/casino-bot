"""
Manages franchise bots running in the same asyncio process,
sharing the main Dispatcher and all game handlers.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logger = logging.getLogger(__name__)

# Set by main.py after creating the Dispatcher — avoids circular imports.
MAIN_DP: Dispatcher | None = None

# Maps bot_id (int) → franchise owner's Telegram user_id.
# Used by start.py to auto-link new users to the franchise owner.
FRANCHISE_BOT_MAP: dict[int, int] = {}


async def start_franchise_bot(dp: Dispatcher, token: str, owner_id: int) -> str | None:
    """
    Start one franchise bot that shares the main Dispatcher.
    Returns the bot username on success, None on failure.
    """
    try:
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        info = await bot.get_me()
        FRANCHISE_BOT_MAP[info.id] = owner_id
        asyncio.create_task(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            name=f"franchise-poll-{info.id}",
        )
        logger.info("Started franchise bot @%s (id=%s) for owner %s",
                    info.username, info.id, owner_id)
        return info.username
    except Exception as exc:
        logger.error("Failed to start franchise bot (owner=%s): %s", owner_id, exc)
        return None


async def load_all_franchise_bots(dp: Dispatcher):
    """Called once at startup to resume all active franchise bots from DB."""
    from database.db import get_active_franchises
    rows = await get_active_franchises()
    for row in rows:
        await start_franchise_bot(dp, row["bot_token"], row["owner_id"])
    if rows:
        logger.info("Loaded %d franchise bot(s) from DB", len(rows))
