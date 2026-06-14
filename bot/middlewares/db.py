from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from typing import (
    Callable, Dict,
    Any, Awaitable
)

from backend.database.session import async_session
from backend.services import (
    UserService, TransactionService, BillingService, 
    SubscriptionService, PromoService,
    ReferralService, WithdrawalService, DeviceService, RemnaWaveService,
    PartnerService,
)

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
            except Exception:
                await session.rollback()
                logger.exception("Database error while handling update")
                await self._notify_database_error(event)
                return None
            finally:
                try:
                    await billing_service.close_clients()
                except Exception:
                    pass
                await session.close()

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
