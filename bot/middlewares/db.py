from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from typing import (
    Callable, Dict,
    Any, Awaitable
)

from sqlalchemy.exc import DBAPIError, InterfaceError

from backend.database.session import async_session
from backend.services import (
    UserService, TransactionService, BillingService, 
    SubscriptionService, PromoService,
    ReferralService, WithdrawalService, DeviceService, RemnaWaveService,
    PartnerService,
)

from backend.core.logger_config import logger


def _is_connection_closed_error(exc: Exception) -> bool:
    if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
        return True

    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "connection is closed",
            "connection was closed",
            "server closed the connection unexpectedly",
            "connection already closed",
        )
    ) or isinstance(exc, InterfaceError)


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(2):
            billing_service: BillingService | None = None
            async with async_session() as session:
                data["session"] = session
                data["user_service"] = UserService(session)
                data["transaction_service"] = TransactionService(session)
                billing_service = BillingService(session)
                data["billing_service"] = billing_service
                data["subscription_service"] = SubscriptionService(session)
                data["promo_service"] = PromoService(session)
                data["referral_service"] = ReferralService(session)
                data["withdrawal_service"] = WithdrawalService(session)
                data["device_service"] = DeviceService(session)
                data["remnawave_service"] = RemnaWaveService(session)
                data["partner_service"] = PartnerService(session)

                try:
                    result = await handler(event, data)
                    await session.commit()
                    return result
                except Exception as exc:
                    last_error = exc
                    try:
                        await session.rollback()
                    except Exception:
                        pass

                    if attempt == 0 and _is_connection_closed_error(exc):
                        logger.warning("Database connection was closed, retrying update once")
                        continue

                    logger.exception("Database error while handling update")
                    await self._notify_database_error(event)
                    return None
                finally:
                    try:
                        await billing_service.close_clients()
                    except Exception:
                        pass
                    await session.close()

        return None

    async def _notify_database_error(self, event: Message | CallbackQuery) -> None:
        text = (
            "Сервис временно недоступен из-за ошибки базы данных. "
            "Попробуйте еще раз через несколько секунд."
        )
        try:
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        "Ошибка сервиса. Попробуйте еще раз через несколько секунд.",
                        show_alert=True
                    )
                except Exception:
                    pass
                if event.message:
                    await event.message.answer(text)
                return

            if isinstance(event, Message):
                await event.answer(text)
        except Exception:
            pass
