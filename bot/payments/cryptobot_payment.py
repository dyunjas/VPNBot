from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.core.logger_config import logger
from backend.images import PROFILE_IMG
from backend.services.exceptions import UserNotFound
from backend.states import PaymentStates
from bot.payments import messages as payment_messages
from bot.payments.keyboards import payment_menu_kb

router = Router()


@router.callback_query(
    F.data == "pay_cryptobot",
    PaymentStates.waiting_for_payment_system,
)
async def pay_crypto_clb(
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
    amount_rub: int | None = data.get("amount")
    if not amount_rub:
        await state.set_state(PaymentStates.waiting_for_amount)
        await callback.answer(payment_messages.AMOUNT_NOT_FOUND, show_alert=True)
        return

    logger.info(f"[CRYPTO] Create invoice tg_id={tg_id} amount={amount_rub} RUB")

    try:
        invoice = await bot_api.create_crypto_invoice(
            tg_id=tg_id,
            amount_rub=amount_rub,
            asset="USDT",
            description=f"Пополнение баланса на {amount_rub} RUB",
        )
    except Exception as e:
        logger.exception(f"[CRYPTO] Payment creation failed for tg_id={tg_id}: {e}")
        await callback.answer(payment_messages.CREATE_ERROR, show_alert=True)
        return

    payload = invoice.get("invoice") if isinstance(invoice, dict) else invoice
    invoice_id = payload.get("invoice_id")
    pay_url = payload.get("pay_url")
    if not invoice_id or not pay_url:
        await callback.answer(payment_messages.CREATE_ERROR, show_alert=True)
        return

    await callback.message.edit_media(
        InputMediaPhoto(
            media=PROFILE_IMG,
            caption=payment_messages.created_auto_caption(
                method_name="CryptoBot",
                transaction_id=str(invoice_id),
            ),
            parse_mode="HTML",
        ),
        reply_markup=payment_menu_kb(
            invoice_url=pay_url,
        ),
    )

    await state.update_data(invoice_id=invoice_id)
    await callback.answer()
