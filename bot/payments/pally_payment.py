from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.core.logger_config import logger
from backend.images import PROFILE_IMG
from backend.services.exceptions import PaymentNotConfirmed, TransactionNotFound, UserNotFound
from backend.states import PaymentStates
from bot.payments import messages as payment_messages
from bot.payments.keyboards import back_profile_kb, payment_menu_kb

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
            caption=payment_messages.created_caption(
                method_name="СБП 1",
                transaction_id=transaction_id,
            ),
            parse_mode="HTML",
        ),
        reply_markup=payment_menu_kb(
            invoice_url=redirect_url,
            invoice_id=transaction_id,
            check_prefix="check_payment_pally",
        ),
    )

    await state.update_data(invoice_id=transaction_id)
    await callback.answer()


@router.callback_query(F.data.startswith("check_payment_pally:"))
async def check_pally_payment_clb(
    callback: CallbackQuery,
    state: FSMContext,
    bot_api,
):
    transaction_id = callback.data.split(":", 1)[1]

    try:
        result = await bot_api.confirm_pally_payment(
            tg_id=callback.from_user.id,
            provider_transaction_id=transaction_id,
        )
    except PaymentNotConfirmed:
        await callback.answer(payment_messages.NOT_CONFIRMED, show_alert=True)
        return
    except UserNotFound:
        await callback.answer(payment_messages.USER_NOT_FOUND, show_alert=True)
        return
    except TransactionNotFound:
        await callback.answer(payment_messages.TRANSACTION_NOT_FOUND, show_alert=True)
        return
    except Exception as e:
        logger.exception(f"[PALLY] Unexpected error confirming payment {transaction_id}: {e}")
        await callback.answer(payment_messages.CONFIRM_ERROR, show_alert=True)
        return

    amount_display = int(result.get("transaction", {}).get("amount", 0) or 0)
    bonus = int(result.get("referral_bonus") or 0)
    referrer_tg_id = result.get("referrer_tg_id")
    if bonus > 0 and referrer_tg_id:
        try:
            await callback.bot.send_message(
                chat_id=referrer_tg_id,
                text=payment_messages.referral_bonus_caption(
                    bonus_rub=bonus,
                    payment_amount_rub=amount_display,
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await callback.message.edit_media(
        InputMediaPhoto(
            media=PROFILE_IMG,
            caption=payment_messages.success_caption(amount_rub=amount_display),
            parse_mode="HTML",
        ),
        reply_markup=back_profile_kb(),
    )

    await state.clear()
    await callback.answer()
