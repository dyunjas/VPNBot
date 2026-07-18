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
    F.data == "pay_pally",
    PaymentStates.waiting_for_payment_system,
)
async def pay_pally_clb(
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

    logger.info(f"[PALLY] Create payment tg_id={tg_id} amount={amount}")

    try:
        payment = await bot_api.create_pally_payment(
            tg_id=tg_id,
            amount=float(amount),
            description=f"Пополнение баланса на {amount} RUB",
            return_url="https://t.me/LunetVpnBot",
            failed_url="https://t.me/LunetVpnBot",
        )
    except Exception as e:
        logger.exception(f"[PALLY] Payment creation failed for tg_id={tg_id}: {e}")
        await callback.answer(payment_messages.CREATE_ERROR, show_alert=True)
        return

    payload = payment.get("payment") if isinstance(payment, dict) else payment
    transaction_id = str(payload.get("id"))
    redirect_url = (
        payload.get("payment_url")
        or payload.get("pay_url")
        or payload.get("url")
        or payload.get("link")
        or payload.get("link_page_url")
        or payload.get("redirect")
    )
    if not transaction_id or not redirect_url:
        await callback.answer(payment_messages.CREATE_ERROR, show_alert=True)
        return

    await callback.message.edit_media(
        InputMediaPhoto(
            media=PROFILE_IMG,
            caption=payment_messages.created_auto_caption(
                method_name="СБП 1",
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
