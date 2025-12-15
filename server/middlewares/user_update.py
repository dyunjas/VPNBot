from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, User

from typing import (
    Callable, Dict,
    Any, Awaitable
)

from sqlalchemy.ext.asyncio import AsyncSession

from server.repositories.user_repository import UserRepository

class UserUpdateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        event_user: User = data.get("event_from_user")
        session: AsyncSession = data.get("session")

        if event_user and session:
            user_repo = UserRepository(session)

            await self._check_or_create_user(event_user, user_repo)

        return await handler(event, data)
    
    async def _check_or_create_user(self, tg_user: User, user_repo: UserRepository):
        user = await user_repo.get_user_by_tg_id(tg_user.id)
        if user:
            if user.username != tg_user.username:
                await user_repo.update_username(user.tg_id, tg_user.username)
        else:
            await user_repo.create_user(
                tg_id=tg_user.id,
                username=tg_user.username
            )
            await user_repo.session.flush() 