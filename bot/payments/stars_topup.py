from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery

from backend.core.logger_config import logger

router = Router()

ADMIN_STARS_TOPUP_PREFIX = "admin_stars_topup:"


@router.pre_checkout_query(F.invoice_payload.startswith(ADMIN_STARS_TOPUP_PREFIX))
async def admin_stars_topup_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def admin_stars_topup_success(message: Message):
    payment = message.successful_payment
    if not payment or not str(payment.invoice_payload or "").startswith(ADMIN_STARS_TOPUP_PREFIX):
        return

    logger.info(
        "[bot][stars] admin_stars_topup_paid tg_id=%s charge_id=%s amount=%s currency=%s payload=%s",
        message.from_user.id if message.from_user else None,
        payment.telegram_payment_charge_id,
        payment.total_amount,
        payment.currency,
        payment.invoice_payload,
    )
