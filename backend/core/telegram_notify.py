from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from backend.core import loader
from backend.core.config import settings
from backend.core.logger_config import logger
from backend.core.telegram import create_telegram_session


async def send_telegram_message_safe(
    *,
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup=None,
    log_prefix: str = "[telegram]",
) -> bool:
    bot_instance = loader.bot
    temp_bot: Bot | None = None
    if bot_instance is None:
        bot_token = (settings.BOT_TOKEN or "").strip()
        if not bot_token:
            logger.warning("%s notify skipped: BOT_TOKEN is not configured chat_id=%s", log_prefix, chat_id)
            return False
        temp_bot = Bot(token=bot_token, session=create_telegram_session())
        bot_instance = temp_bot

    try:
        await bot_instance.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return True
    except TelegramForbiddenError:
        logger.warning("%s notify skipped: bot blocked by user chat_id=%s", log_prefix, chat_id)
        return False
    except Exception:
        logger.exception("%s notify failed chat_id=%s", log_prefix, chat_id)
        return False
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()
