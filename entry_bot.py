import asyncio

from backend.core.loader import (
    setup_bot,
    shutdown_bot
)

from bot.middlewares.db import DBSessionMiddleware
from bot.middlewares.user_update import UserUpdateMiddleware

from bot import bot_routers

from backend.core.logger_config import logger

async def main():
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
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        if bot:
            await shutdown_bot(bot)
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
