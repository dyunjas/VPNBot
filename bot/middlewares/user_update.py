from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from backend.core.logger_config import logger
from backend.services.exceptions import UserNotFound


class UserUpdateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        event_user: TgUser | None = data.get("event_from_user")
        bot_api = data.get("bot_api")

        if not event_user or bot_api is None:
            return await handler(event, data)

        try:
            user = await bot_api.get_user_by_tg_id(event_user.id)
        except UserNotFound:
            data["is_new_user"] = True
            return await handler(event, data)
        except Exception as e:
            logger.exception("Failed to load user from API: %s", e)
            return None

        data["is_new_user"] = False
        data["user"] = user.get("user") if isinstance(user, dict) else user

        user_payload = data["user"] or {}
        if bool(user_payload.get("banned")):
            await self._notify_banned(event, int(user_payload.get("tg_id") or event_user.id))
            return None

        if user_payload.get("username") != event_user.username:
            try:
                await bot_api.update_username(user_id=int(user_payload["id"]), username=event_user.username)
            except Exception:
                logger.exception("Failed to sync username for tg_id=%s", event_user.id)

        return await handler(event, data)

    async def _notify_banned(self, event: TelegramObject, tg_id: int) -> None:
        text = (
            "<b>Ваш аккаунт заблокирован.</b>\n\n"
            "Для дополнительной информации свяжитесь со службой поддержки @LunetVPNSupport."
        )
        try:
            bot = getattr(event, "bot", None)
            if bot:
                await bot.send_message(chat_id=tg_id, text=text)
        except Exception:
            pass

