from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from server.core.config import settings

bot = Bot(
    token=settings.BOT_TOKEN
)

async def setup_bot() -> tuple[Bot, Dispatcher]:
    default = DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        link_preview_is_disabled=True
    )

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=default
    )

    dp = Dispatcher(storage=MemoryStorage())
    return bot, dp

async def shutdown_bot(bot: Bot):
    await bot.session.close()


