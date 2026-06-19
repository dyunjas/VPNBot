from typing import Awaitable, Callable, Any, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import UserService
from backend.services.exceptions import UserNotFound


class UserUpdateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        event_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")

        if not event_user or not session:
            return await handler(event, data)

        user_service = UserService(session)
        data["user_service"] = user_service

        try:
            user = await user_service.get_by_tg_id(event_user.id)
        except UserNotFound:
            data["is_new_user"] = True
            return await handler(event, data)

        data["is_new_user"] = False
        data["user"] = user

        if getattr(user, "banned", False):
            await self._notify_banned(event, user.tg_id)
            return None

        if user.username != event_user.username:
            await user_service.set_username(user.id, event_user.username)

        return await handler(event, data)

    async def _notify_banned(self, event: TelegramObject, tg_id: int) -> None:
        text = (
            "<b>🚫 Ваш аккаунт заблокирован.</b>\n\n"
            "Для дополнительной информации свяжитесь со службой поддержки @LunetVPNSupport."
        )
        try:
            bot = getattr(event, "bot", None)
            if bot:
                await bot.send_message(chat_id=tg_id, text=text)
        except Exception:
            pass
