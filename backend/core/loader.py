from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from backend.api_client import BotApiClient
from backend.core.config import settings
from backend.core.telegram import create_telegram_session

default = DefaultBotProperties(
    parse_mode=ParseMode.HTML,
    link_preview_is_disabled=True,
)

bot: Bot | None = None
dp: Dispatcher | None = None
bot_api: BotApiClient | None = None


async def setup_bot():
    global bot, dp, bot_api

    session = create_telegram_session()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=default,
        session=session,
    )

    dp = Dispatcher(storage=MemoryStorage())
    bot_api = BotApiClient()

    return bot, dp


async def shutdown_bot(bot: Bot):
    await bot.session.close()
    if bot_api is not None:
        await bot_api.close()
