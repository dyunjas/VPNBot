from __future__ import annotations

import asyncio

from backend.core.loader import setup_bot, shutdown_bot
from bot import bot_routers
from bot.middlewares.db import DBSessionMiddleware
from bot.middlewares.user_update import UserUpdateMiddleware
from backend.core.logger_config import logger


async def run_bot() -> None:
    bot = None
    try:
        bot, dp = await setup_bot()
        dp.update.middleware(DBSessionMiddleware())
        dp.update.middleware(UserUpdateMiddleware())
        dp.include_router(bot_routers.router)

        logger.info("Bot started")
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled")
        raise
    except Exception as exc:
        logger.exception("Bot crashed: %s", exc)
    finally:
        if bot is not None:
            await shutdown_bot(bot)
        logger.info("Bot stopped")

