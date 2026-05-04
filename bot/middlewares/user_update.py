from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, User as TgUser
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Callable, Dict, Any, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession
from backend.services import UserService, SubscriptionService
from backend.services.exceptions import UserNotFound


class UserUpdateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        event_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")

        if not event_user or not session:
            return await handler(event, data)

        user_service = UserService(session)
        data["user_service"] = user_service

        try:
            user = await user_service.get_by_tg_id(event_user.id)
            data["is_new_user"] = False
        except UserNotFound:
            user = await user_service.create_user(
                tg_id=event_user.id,
                username=event_user.username
            )
            data["is_new_user"] = True
            await self._grant_trial_and_notify(event, session, user.tg_id, user.id)

        # Avoid lazy-loading attributes from a possibly expired ORM instance after inner commits.
        user = await user_service.get_by_tg_id(event_user.id)
        data["user"] = user

        if getattr(user, "banned", False):
            await self._notify_banned(event, user.tg_id)
            return

        if user.username != event_user.username:
            await user_service.set_username(user.id, event_user.username)

        return await handler(event, data)

    async def _grant_trial_and_notify(
        self,
        event: TelegramObject,
        session: AsyncSession,
        tg_id: int,
        user_id: int,
    ) -> None:
        sub_service = SubscriptionService(session)
        try:
            await sub_service.activate_subscription(
                user_id=user_id,
                plan_id=9,
                auto_renew=False,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            return

        text = (
            "<tg-emoji emoji-id='5875180111744995604'>🎁</tg-emoji> <b>Вам выдан тестовый период.</b>\n\n"
            "Перейдите в меню «Подписка», чтобы посмотреть детали."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="🌙 Подписка", callback_data="vpn_subscription")
        markup = builder.as_markup()
        try:
            if isinstance(event, Message):
                await event.answer(text, reply_markup=markup)
                return

            if isinstance(event, CallbackQuery):
                if event.message:
                    await event.message.answer(text, reply_markup=markup)
                else:
                    await event.bot.send_message(chat_id=tg_id, text=text, reply_markup=markup)
                return

            bot = getattr(event, "bot", None)
            if bot:
                await bot.send_message(chat_id=tg_id, text=text, reply_markup=markup)
        except Exception:
            pass

    async def _notify_banned(self, event: TelegramObject, tg_id: int) -> None:
        text = (
            "<b>🚫 Ваш аккаунт заблокирован.</b>\n\n"
            "Для дополнительной информации свяжитесь со службой поддержки @LunetVPNSupportBot."
        )
        try:
            if isinstance(event, Message):
                await event.answer(text)
                return

            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
                if event.message:
                    await event.message.answer(text)
                else:
                    await event.bot.send_message(chat_id=tg_id, text=text)
                return

            bot = getattr(event, "bot", None)
            if bot:
                await bot.send_message(chat_id=tg_id, text=text)
        except Exception:
            pass
