import asyncio
from contextlib import suppress

from backend.core.loader import (
    setup_bot,
    shutdown_bot
)

from backend.database.session import (
    init_db,
    check_connection,
    engine
)

from bot.middlewares.db import DBSessionMiddleware
from bot.middlewares.user_update import UserUpdateMiddleware

from bot import bot_routers

from backend.core.logger_config import logger

from backend.schedulers.expire_checker import expire_checker_loop

async def main():
    bot = None
    checker_task = None
    try:
        bot, dp = await setup_bot()

        await init_db()
        await check_connection()

        dp.update.middleware(DBSessionMiddleware())
        dp.update.middleware(UserUpdateMiddleware())

        dp.include_router(bot_routers.router)

        checker_task = asyncio.create_task(
            expire_checker_loop(bot, interval_sec=7200)
        )

        logger.info("Bot started")
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled")
        raise
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        if checker_task:
            checker_task.cancel()
            with suppress(asyncio.CancelledError):
                await checker_task
        if bot:
            await shutdown_bot(bot)
        await engine.dispose()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
