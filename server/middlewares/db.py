from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from typing import (
    Callable, Dict,
    Any, Awaitable
)

from server.database.session import async_session

from server.repositories.user_repository import UserRepository
from server.repositories.subscription_repository import SubscriptionRepository
from server.repositories.key_repository import KeyRepository
from server.repositories.server_repository import ServerRepository
from server.repositories.promocode_repository import PromocodeRepository
from server.repositories.transaction_repository import TransactionRepository

from server.core.logger_config import logger

class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            data["user_repo"] = UserRepository(session)
            data["subscription_repo"] = SubscriptionRepository(session)
            data["key_repo"] = KeyRepository(session)
            data["server_repo"] = ServerRepository(session)
            data["promocode_repo"] = PromocodeRepository(session)
            data["transaction_repo"] = TransactionRepository(session)

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Database error: {e}")
            finally:
                await session.close()