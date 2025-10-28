# bot/handlers/payments_platega_handlers.py
from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from server.images import MAIN_MENU_IMG
from client.payments.keyboards import back_profile_kb, payment_menu_kb

from server.states import PaymentStates
from server.core.logger_config import logger

from server.payments.generate_platega_invoice import PlategaPaymentAPI  # <-- клиент Platega
from server.repositories.user_repository import UserRepository
from server.repositories.transaction_repository import TransactionRepository

router = Router()

_platega_client: PlategaPaymentAPI | None = None
def platega() -> PlategaPaymentAPI:
    global _platega_client
    if _platega_client is None:
        _platega_client = PlategaPaymentAPI()
    return _platega_client


@router.callback_query(F.data == "pay_platega", PaymentStates.waiting_for_payment_system)
async def pay_platega_clb(
    callback: CallbackQuery,
    state: FSMContext,
    transaction_repo: TransactionRepository,
):
    tg_id = callback.from_user.id
    data = await state.get_data()
    amount = data.get("amount")

    logger.info(f"[PLATEGA] Received data: tg_id={tg_id} data={data}")

    order_id = f"TPU-{tg_id}-{int(datetime.now().timestamp())}"

    resp = await platega().create_payment(
        amount=float(amount),
        currency="RUB",
        payment_method=2,
        description=f"Пополнение баланса на {amount} RUB",
        return_url="https://t.me/shopchek_bot",
        failed_url="https://t.me/shopchek_bot",
        payload=order_id,
    )

    http_status = resp.get("http_status", 200)
    if http_status >= 400:
        logger.error(f"[PLATEGA] HTTP error {http_status}: {resp}")
        await callback.answer(f"❌ Ошибка создания счёта: HTTP {http_status}", show_alert=True)
        return

    transaction_id: str | None = resp.get("transactionId")
    redirect_url: str | None = resp.get("redirect") or resp.get("payformSuccessUrl")
    status: str | None = resp.get("status")

    if not transaction_id:
        logger.error(f"[PLATEGA] create_payment: нет transactionId в ответе: {resp}")
        await callback.answer("❌ Не удалось создать транзакцию (нет transactionId).", show_alert=True)
        return

    try:
        await transaction_repo.create_transaction(
            tg_id=tg_id,
            transaction_id=transaction_id,
            amount=int(float(amount)),
            payment_system="PLATEGA",
            order_id=order_id,
        )
    except Exception as e:
        logger.exception(f"[PLATEGA] Error creating transaction: {e}")

    text = (
        "💳 Счёт создан, перейдите по ссылке для оплаты!\n"
        f"<pre><code>ID транзакции: {transaction_id}</code></pre>\n"
    )
    content = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
    )

    await callback.message.edit_media(
        media=content,
        reply_markup=payment_menu_kb(
            invoice_url=redirect_url or "",
            invoice_id=transaction_id,
            check_prefix="check_payment_platega",
        ),
    )
    await state.update_data(order_id=order_id, invoice_id=transaction_id)
    await callback.answer()


@router.callback_query(F.data.startswith("check_payment_platega:"))
async def check_platega_payment_clb(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    transaction_repo: TransactionRepository,
):
    tg_id = callback.from_user.id
    transaction_id = callback.data.split(":", 1)[1]

    transaction = await transaction_repo.get_transaction_by_payment_system_id(transaction_id)
    if not transaction or transaction.user.tg_id is None:
        await callback.answer("Транзакция не найдена.", show_alert=True)
        return

    resp = await platega().get_status(transaction_id)
    http_status = resp.get("http_status", 200)
    if http_status == 404:
        await callback.answer("Платёж не найден в системе Platega (404).", show_alert=True)
        logger.error(f"[PLATEGA] status 404 for {transaction_id}: {resp}")
        return
    if http_status >= 400:
        await callback.answer(f"Ошибка запроса: HTTP {http_status}", show_alert=True)
        logger.error(f"[PLATEGA] status error {http_status} for {transaction_id}: {resp}")
        return
    status: str = (resp.get("status") or "").upper()

    if status == "CONFIRMED":
        if getattr(transaction, "paid", False):
            await callback.answer("✅ Платёж уже подтверждён.", show_alert=True)
            return

        await user_repo.increase_balance(tg_id, transaction.amount)
        await transaction_repo.mark_transaction_as_paid(transaction_id)

        text = (
            f"✅ Оплата успешно завершена!\n"
            f"<b>🌟 Баланс пополнен на:</b> {transaction.amount} RUB."
        )
        content = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
        await callback.message.edit_media(media=content, reply_markup=back_profile_kb())

        logger.info(f"[PLATEGA] Payment successful tg_id={tg_id} id={transaction_id} amount={transaction.amount}")
        await state.clear()
        await callback.answer()
        return

    if status in {"CREATED", "PENDING", "INPROGRESS"}:
        await callback.answer("⏳ Платёж ещё не подтверждён. Попробуйте позже.", show_alert=True)
        return

    if status in {"FAILED", "EXPIRED", "CANCELED"}:
        map_human = {
            "FAILED": "ошибка/отклонён",
            "EXPIRED": "просрочен",
            "CANCELED": "отменён",
        }
        await callback.answer(
            f"⚠️ Оплата не завершена. Статус: {map_human.get(status, status)}.",
            show_alert=True,
        )
        return
    
    await callback.answer(f"Статус платежа: {status or 'UNKNOWN'}", show_alert=True)
