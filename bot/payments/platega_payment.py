from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from backend.images import MAIN_MENU_IMG
from bot.payments.keyboards import back_profile_kb, payment_menu_kb
from backend.states import PaymentStates
from backend.core.logger_config import logger
from backend.services import BillingService, UserService
from backend.services.exceptions import UserNotFound, PaymentNotConfirmed, TransactionNotFound

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
    billing_service: BillingService,
    user_service: UserService
):
    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    data = await state.get_data()
    amount: int | None = data.get("amount")

    if not amount:
        await callback.message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Сумма не найдена", show_alert=True)
        return

    method = callback.data.split(":", 1)[1]

    if method == "sbp":
        method_name = "СБП"
        payment_method = PLATEGA_SBP
    elif method == "card":
        method_name = "Банковская карта"
        payment_method = PLATEGA_CARD
    else:
        await callback.message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Неизвестный способ оплаты", show_alert=True)
        return

    logger.info(f"[PLATEGA] Create payment tg_id={user.id} amount={amount} method={method_name}")

    try:
        payment = await billing_service.create_platega_payment(
            user_id=user.id,
            amount=float(amount),
            description=f"Пополнение баланса на {amount} RUB",
            return_url="https://t.me/LunetVpnBot",
            failed_url="https://t.me/LunetVpnBot",
            payment_method=payment_method
        )
    except Exception as e:
        logger.error(f"[PLATEGA] Payment creation failed for tg_id={user.id}: {e}")
        await callback.message.answer(f"<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ошибка создания платежа: {e}", show_alert=True)
        return

    transaction_id = str(payment.get("id"))
    redirect_url = payment.get("redirect") or payment.get("payformSuccessUrl")

    if not transaction_id or not redirect_url:
        await callback.message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ошибка создания платежа", show_alert=True)
        return

    await callback.message.edit_media(
        InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=(
                "<tg-emoji emoji-id='5927169041595634481'>💳</tg-emoji> Счёт создан, перейдите по ссылке для оплаты!\n"
                f"<b>Способ оплаты:</b> {method_name}\n"
                f"<pre>ID транзакции: {transaction_id}</pre>"
            ),
            parse_mode="HTML",
        ),
        reply_markup=payment_menu_kb(
            invoice_url=redirect_url,
            invoice_id=transaction_id,
            check_prefix="check_payment_platega",
        ),
    )

    await state.update_data(invoice_id=transaction_id)
    await callback.answer()


@router.callback_query(F.data.startswith("check_payment_platega:"))
async def check_platega_payment_clb(
    callback: CallbackQuery,
    state: FSMContext,
    billing_service: BillingService,
    user_service: UserService,
):
    transaction_id = callback.data.split(":", 1)[1]

    try:
        tx = await billing_service.confirm_platega_payment(transaction_id)
    except (UserNotFound, TransactionNotFound, PaymentNotConfirmed) as e:
        await callback.message.answer(
            f"<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> {e}",
            show_alert=True
        )
        return
    except Exception as e:
        logger.exception(f"[PLATEGA] Unexpected error confirming payment {transaction_id}: {e}")
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Произошла ошибка при подтверждении платежа",
            show_alert=True
        )
        return

    amount_display = getattr(tx, "amount", 0)

    try:
        tx_user_id = getattr(tx, "user_id", None)
        if tx_user_id is not None:
            payer = await user_service.get_by_id(int(tx_user_id))

            referrer_id = getattr(payer, "referrer_id", None)
            if referrer_id:
                bonus = int(round(float(amount_display) * 0.20))

                if bonus > 0:
                    await user_service.add_balance(int(referrer_id), bonus)

                    try:
                        referrer = await user_service.get_by_id(int(referrer_id))
                        await callback.bot.send_message(
                            chat_id=referrer.tg_id,
                            text=(
                                "<tg-emoji emoji-id='5994502837327892086'>🎉</tg-emoji> Бонус за реферала!\n"
                                f"<b>Начислено:</b> {bonus} RUB (20% от платежа реферала)"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.exception(f"[REF] Failed to начислить 20% referrer for tx={transaction_id}: {e}")

    await callback.message.edit_media(
        InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=(
                "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Оплата успешна!\n"
                f"<b>Баланс пополнен на:</b> {amount_display} RUB"
            ),
            parse_mode="HTML",
        ),
        reply_markup=back_profile_kb(),
    )

    await state.clear()
    await callback.answer()
