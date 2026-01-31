from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from typing import (
    Callable, Dict,
    Any, Awaitable
)

from backend.database.session import async_session
from backend.services import (
    UserService, TransactionService, BillingService, 
    SubscriptionService, VPNService, PromoService
)

from backend.core.config import settings

from backend.core.logger_config import logger

class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            data["user_service"] = UserService(session)
            data["transaction_service"] = TransactionService(session)
            data["billing_service"] = BillingService(session)
            data["subscription_service"] = SubscriptionService(session)
            data["vpn_service"] = VPNService(session, xray_auth_token=settings.XRAY_AUTH)
            data["promo_service"] = PromoService(session)

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Database error: {e}")
            finally:
                await session.close()