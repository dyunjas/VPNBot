from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

from backend.core.config import settings

default = DefaultBotProperties(
    parse_mode=ParseMode.HTML,
    link_preview_is_disabled=True,
)

bot: Bot | None = None
dp: Dispatcher | None = None


async def setup_bot():
    global bot, dp

    proxy_url = settings.BOT_PROXY  # socks5://user:pass@ip:port

    # ✅ ВАЖНО: прокси тут, без aiohttp_socks
    session = AiohttpSession(proxy=proxy_url)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=default,
        session=session,
    )

    dp = Dispatcher(storage=MemoryStorage())

    return bot, dp


async def shutdown_bot(bot: Bot):
    await bot.session.close()