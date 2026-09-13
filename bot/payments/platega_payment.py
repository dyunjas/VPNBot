from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.core.logger_config import get_logger

logger = get_logger("payments")
from backend.images import PROFILE_IMG
from backend.services.exceptions import UserNotFound
from backend.states import PaymentStates
from bot.payments import messages as payment_messages
from bot.payments.keyboards import payment_menu_kb

router = Router()

PLATEGA_CARD = 11
PLATEGA_SBP = 2


@router.callback_query(
    F.data.startswith("pay_platega:"),
    PaymentStates.waiting_for_payment_system,
)
async def pay_platega_clb(
    callback: CallbackQuery,
    state: FSMContext,
    bot_api,
):
    tg_id = callback.from_user.id

    try:
        await bot_api.get_user_by_tg_id(tg_id)
    except UserNotFound:
        await callback.answer(payment_messages.USER_NOT_FOUND, show_alert=True)
        return

    data = await state.get_data()
    amount: int | None = data.get("amount")
    if not amount:
        await state.set_state(PaymentStates.waiting_for_amount)
        await callback.answer(payment_messages.AMOUNT_NOT_FOUND, show_alert=True)
        return

    method = callback.data.split(":", 1)[1]
    if method == "sbp":
        method_name = "СБП 2"
        payment_method = PLATEGA_SBP
    elif method == "card":
        method_name = "Банковская карта"
        payment_method = PLATEGA_CARD
    else:
        await callback.answer(payment_messages.UNKNOWN_METHOD, show_alert=True)
        return

    logger.info(f"[PLATEGA] Create payment tg_id={tg_id} amount={amount} method={method_name}")

    try:
        payment = await bot_api.create_platega_payment(
            tg_id=tg_id,
            amount=float(amount),
            description=f"Пополнение баланса на {amount} RUB",
            return_url="https://t.me/LunetVpnBot",
            failed_url="https://t.me/LunetVpnBot",
            payment_method=payment_method,
        )
    except Exception as e:
        logger.exception(f"[PLATEGA] Payment creation failed for tg_id={tg_id}: {e}")
        await callback.answer(payment_messages.CREATE_ERROR, show_alert=True)
        return

    payload = payment.get("payment") if isinstance(payment, dict) else payment
    transaction_id = str(payload.get("id"))
    redirect_url = payload.get("redirect") or payload.get("payformSuccessUrl")
    if not transaction_id or not redirect_url:
        await callback.answer(payment_messages.CREATE_ERROR, show_alert=True)
        return

    await callback.message.edit_media(
        InputMediaPhoto(
            media=PROFILE_IMG,
            caption=payment_messages.created_auto_caption(
                method_name=method_name,
                transaction_id=transaction_id,
            ),
            parse_mode="HTML",
        ),
        reply_markup=payment_menu_kb(
            invoice_url=redirect_url,
        ),
    )

    await state.update_data(invoice_id=transaction_id)
    await callback.answer()
