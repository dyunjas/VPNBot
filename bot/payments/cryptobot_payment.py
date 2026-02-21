from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from backend.images import MAIN_MENU_IMG
from bot.payments.keyboards import back_profile_kb, payment_menu_kb
from backend.states import PaymentStates
from backend.core.logger_config import logger
from backend.services import UserService, BillingService
from backend.services.referral_service import ReferralService
from backend.services.exceptions import (
    UserNotFound,
    PaymentNotConfirmed,
    TransactionNotFound,
)

router = Router()


@router.callback_query(
    F.data == "pay_cryptobot",
    PaymentStates.waiting_for_payment_system,
)
async def pay_crypto_clb(
    callback: CallbackQuery,
    state: FSMContext,
    billing_service: BillingService,
    user_service: UserService,
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
    amount_rub: int | None = data.get("amount")

    if not amount_rub:
        await callback.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Сумма не найдена", show_alert=True)
        return

    logger.info(f"[CRYPTO] Create invoice id={user.id} amount={amount_rub} RUB")

    invoice = await billing_service.create_crypto_invoice(
        user_id=user.id,
        amount_rub=amount_rub,
        asset="USDT",
        description=f"Пополнение баланса на {amount_rub} RUB",
    )

    invoice_id = invoice.get("invoice_id")
    pay_url = invoice.get("pay_url")

    if not invoice_id or not pay_url:
        await callback.message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ошибка создания крипто-счёта", show_alert=True)
        return

    await callback.message.edit_media(
        InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=(
                "<tg-emoji emoji-id='5992430854909989581'>🪙</tg-emoji> Счёт создан, перейдите по ссылке для оплаты!\n"
                f"<b>Способ оплаты:</b> CryptoBot\n"
                f"<pre>ID транзакции: {invoice_id}</pre>"
            ),
            parse_mode="HTML",
        ),
        reply_markup=payment_menu_kb(
            invoice_url=pay_url,
            invoice_id=str(invoice_id),
            check_prefix="check_payment_crypto",
        ),
    )

    await state.update_data(invoice_id=invoice_id)
    await callback.answer()


@router.callback_query(F.data.startswith("check_payment_crypto:"))
async def check_crypto_payment_clb(
    callback: CallbackQuery,
    state: FSMContext,
    billing_service: BillingService,
    user_service: UserService,
    referral_service: ReferralService,
):
    invoice_id = int(callback.data.split(":", 1)[1])

    try:
        tx = await billing_service.confirm_crypto_payment(invoice_id)
    except PaymentNotConfirmed:
        await callback.answer("Платеж еще не подтверджен. Попробуйте снова через несолько минут.", show_alert=True)
        return
    except TransactionNotFound:
        await callback.answer("Транзакция не найдена. Если вы совершили оплату - обратитесь в поддержку.", show_alert=True)
        return
    except Exception as e:
        logger.exception(f"[CRYPTO] Unexpected error confirming invoice {invoice_id}: {e}")
        await callback.answer("Ошибка подтверждения платежа. Попробуйте позже.", show_alert=True)
        return

    amount_display = int(getattr(tx, "amount", 0) or 0)

    try:
        tx_user_id = getattr(tx, "user_id", None)
        if tx_user_id is not None and amount_display > 0:
            payer = await user_service.get_by_id(int(tx_user_id))

            bonus = await referral_service.reward_from_purchase(
                user_id=payer.id,
                purchase_amount=amount_display,
            )

            if bonus > 0 and payer.referrer_id:
                try:
                    referrer = await user_service.get_by_id(int(payer.referrer_id))
                    await callback.bot.send_message(
                        chat_id=referrer.tg_id,
                        text=(
                            "<tg-emoji emoji-id='5994502837327892086'>🎉</tg-emoji> Бонус за реферала!\n"
                            f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Начислено:</b> {bonus} RUB\n"
                            f"<b><tg-emoji emoji-id='5769403330761593044'>👛</tg-emoji> Платёж реферала:</b> {amount_display} RUB"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.exception(f"[REF] Failed to начислить процент referrer for crypto tx invoice_id={invoice_id}: {e}")

    await callback.message.edit_media(
        InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=(
                "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Оплата подтверждена!\n"
                f"<b>Баланс пополнен на:</b> {amount_display} RUB"
            ),
            parse_mode="HTML",
        ),
        reply_markup=back_profile_kb(),
    )

    await state.clear()
    await callback.answer()
