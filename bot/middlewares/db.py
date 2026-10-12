from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from backend.core import loader
from backend.core.logger_config import logger
from backend.services.exceptions import MaintenanceModeError
from bot.utils.maintenance import (
    MAINTENANCE_HTML,
    answer_maintenance_callback,
    send_maintenance_message,
)


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if loader.bot_api is None:
            logger.error("Bot API client is not initialized")
            return None

        data["bot_api"] = loader.bot_api
        try:
            return await handler(event, data)
        except MaintenanceModeError:
            logger.warning("Bot request blocked by maintenance mode")
            await self._notify_maintenance(event, data)
            return None
        except Exception:
            user_id = None
            event_user = data.get("event_from_user")
            if event_user is not None:
                user_id = getattr(event_user, "id", None)
            logger.exception(
                "Bot handler failed",
                extra={
                    "app_context": "Telegram Bot",
                    "telegram_user_id": user_id,
                },
            )
            raise

    async def _notify_maintenance(self, event: TelegramObject, data: Dict[str, Any]) -> None:
        callback = self._extract_callback(event, data)
        if callback is not None:
            try:
                await answer_maintenance_callback(callback)
            except Exception:
                logger.exception("Failed to answer maintenance callback")
            return

        message = self._extract_message(event, data)
        if message is not None:
            try:
                await send_maintenance_message(message)
            except Exception:
                logger.exception("Failed to answer maintenance message")
            return

        chat = data.get("event_chat")
        bot = getattr(event, "bot", None) or data.get("bot")
        chat_id = getattr(chat, "id", None)
        if bot is not None and chat_id is not None:
            try:
                await bot.send_message(chat_id=chat_id, text=MAINTENANCE_HTML)
            except Exception:
                logger.exception("Failed to send maintenance fallback message")

    @staticmethod
    def _extract_callback(event: TelegramObject, data: Dict[str, Any]) -> CallbackQuery | None:
        if isinstance(event, CallbackQuery):
            return event
        callback = data.get("callback_query") or getattr(event, "callback_query", None)
        return callback if isinstance(callback, CallbackQuery) else None

    @staticmethod
    def _extract_message(event: TelegramObject, data: Dict[str, Any]) -> Message | None:
        if isinstance(event, Message):
            return event
        for key in ("message", "event_message"):
            candidate = data.get(key)
            if isinstance(candidate, Message):
                return candidate
        for attr in ("message", "edited_message", "channel_post", "edited_channel_post", "business_message", "edited_business_message"):
            candidate = getattr(event, attr, None)
            if isinstance(candidate, Message):
                return candidate
        return None
