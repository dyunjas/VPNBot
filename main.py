import asyncio

from server.core.loader import (
    setup_bot,
    shutdown_bot
)

from server.database.session import (
    init_db,
    check_connection,
    engine
)

from server.middlewares.db import DBSessionMiddleware
from server.middlewares.user_update import UserUpdateMiddleware

from client import client_routers

from server.core.logger_config import logger

from client.vpn_key.expire_checker import expire_checker_loop

async def main():
    try:

        bot, dp = await setup_bot()

        await init_db()
        await check_connection()

        dp.update.middleware(DBSessionMiddleware())
        dp.update.middleware(UserUpdateMiddleware())

        dp.include_router(client_routers.router)

        asyncio.create_task(expire_checker_loop(interval_sec=10))

        logger.info("Bot started")
        await dp.start_polling(bot)


    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        await shutdown_bot(bot)
        await engine.dispose()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())