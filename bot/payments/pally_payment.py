from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from backend.images import MAIN_MENU_IMG
from bot.payments.keyboards import back_profile_kb, payment_menu_kb
from backend.states import PaymentStates
from backend.core.logger_config import logger
from backend.services import BillingService, UserService, ReferralService
from backend.services.exceptions import UserNotFound, PaymentNotConfirmed, TransactionNotFound

router = Router()


@router.callback_query(
    F.data == "pay_pally",
    PaymentStates.waiting_for_payment_system,
)
async def pay_pally_clb(
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
    amount: int | None = data.get("amount")

    if not amount:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Сумма не найдена",
            show_alert=True,
        )
        return

    method_name = "СБП 1"
    logger.info(f"[PALLY] Create payment tg_id={user.id} amount={amount}")

    try:
        payment = await billing_service.create_pally_payment(
            user_id=user.id,
            amount=float(amount),
            description=f"Пополнение баланса на {amount} RUB",
            return_url="https://t.me/LunetVpnBot",
            failed_url="https://t.me/LunetVpnBot",
        )
    except Exception as e:
        logger.error(f"[PALLY] Payment creation failed for tg_id={user.id}: {e}")
        await callback.message.answer(
            f"<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ошибка создания платежа: {e}",
            show_alert=True,
        )
        return

    transaction_id = str(payment.get("id"))
    redirect_url = (
        payment.get("payment_url")
        or payment.get("pay_url")
        or payment.get("url")
        or payment.get("link")
        or payment.get("link_page_url")
        or payment.get("redirect")
    )

    if not transaction_id or not redirect_url:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ошибка создания платежа",
            show_alert=True,
        )
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
            check_prefix="check_payment_pally",
        ),
    )

    await state.update_data(invoice_id=transaction_id)
    await callback.answer()


@router.callback_query(F.data.startswith("check_payment_pally:"))
async def check_pally_payment_clb(
    callback: CallbackQuery,
    state: FSMContext,
    billing_service: BillingService,
    user_service: UserService,
    referral_service: ReferralService,
):
    transaction_id = callback.data.split(":", 1)[1]

    try:
        tx = await billing_service.confirm_pally_payment(transaction_id)
    except (UserNotFound, TransactionNotFound, PaymentNotConfirmed) as e:
        await callback.message.answer(
            f"<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> {e}",
            show_alert=True,
        )
        return
    except Exception as e:
        logger.exception(f"[PALLY] Unexpected error confirming payment {transaction_id}: {e}")
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Произошла ошибка при подтверждении платежа",
            show_alert=True,
        )
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
                            f"<b><tg-emoji emoji-id='5956148757899776734'>💰</tg-emoji> Начислено:</b> {bonus} RUB\n"
                            f"<b><tg-emoji emoji-id='5769403330761593044'>👛</tg-emoji> Платёж реферала:</b> {amount_display} RUB"
                        ),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

    except Exception as e:
        logger.exception(f"[REF] Failed to increase balance referrer for tx={transaction_id}: {e}")

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
