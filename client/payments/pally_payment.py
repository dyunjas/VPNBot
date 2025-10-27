from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from server.images import MAIN_MENU_IMG

from client.payments.keyboards import back_profile_kb, payment_menu_kb

from server.states import PaymentStates

from server.payments.generate_pally_invoice import create_invoice_PALLY, get_invoice_status_PALLY

from datetime import datetime

from server.repositories.user_repository import UserRepository
from server.repositories.transaction_repository import TransactionRepository

from server.core.logger_config import logger

router = Router()

@router.callback_query(F.data == "pay_pally", PaymentStates.waiting_for_payment_system)
async def pay_pally_clb(callback: CallbackQuery, state: FSMContext, transaction_repo: TransactionRepository):
    tg_id = callback.from_user.id
    data = await state.get_data()
    amount = data.get("amount")
    logger.info(f"[PALLY] Received data: {tg_id} {data}")

    order_id = f"TPU-{tg_id}-{int(datetime.now().timestamp())}"

    invoice = await create_invoice_PALLY(
        amount=amount,
        order_id=order_id,
        description=f"Пополнение баланса на {amount} RUB",
        success_url="https://t.me/shopchek_bot",
        fail_url="https://t.me/shopchek_bot"
    )

    if str(invoice.get("success")).lower() == "true":
        invoice_url = invoice.get("link_page_url")
        invoice_id = invoice.get("bill_id")

        try:
            await transaction_repo.create_transaction(
                tg_id=tg_id,
                transaction_id=invoice_id,
                amount=int(amount),
                payment_system="PALLY",
                order_id=order_id
            )
        except Exception as e:
            logger.exception(f"Error creating transaction: {e}")
            pass

        text = (
            "💳 Cчёт создан, перейдите по ссылке для оплаты!\n"
            f"<pre><code>ID транзакции: {invoice_id}</code></pre>\n"
        )
        content = InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=text,
            parse_mode="HTML"
        )
        await callback.message.edit_media(
            media=content,
            reply_markup=payment_menu_kb(invoice_url=invoice_url, invoice_id=invoice_id, check_prefix="check_payment_pally")
        )
        await state.update_data(order_id=order_id, invoice_id=invoice_id)
        await callback.answer()
    else:
        await callback.answer(f"❌ Ошибка создания счёта: {invoice}")
        logger.error(f"PALLY invoice creation error: {invoice.get('error')}")


@router.callback_query(F.data.startswith("check_payment_pally:"))
async def check_pally_payment_clb(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: UserRepository,
    transaction_repo: TransactionRepository
):
    tg_id = callback.from_user.id
    invoice_id = callback.data.split(":")[1]

    transaction = await transaction_repo.get_transaction_by_payment_system_id(invoice_id)
    if not transaction or transaction.user.tg_id is None:
        await callback.answer(
            text="Транзакция не найдена.",
            show_alert=True
        )
        return 

    status_data = await get_invoice_status_PALLY(invoice_id)

    if str(status_data.get("success")).lower() != "true":
        await callback.answer(
            text=f"Ошибка запроса: {status_data}",
            show_alert=True
        )
        logger.error(f"PALLY invoice status error: {status_data.get('error')}")
        return

    invoice_status = status_data.get("status")

    if invoice_status == "SUCCESS":
        if getattr(transaction, 'paid', False):
            await callback.answer(
                text="✅ Платёж уже подтверждён.",
                show_alert=True
            )
            return
        
        await user_repo.increase_balance(tg_id, transaction.amount)
        await transaction_repo.mark_transaction_as_paid(invoice_id)
        text = ( 
            f"✅ Оплата успешно завершена!\n"
            f"<b>🌟 Баланс пополнен на:</b> {transaction.amount} RUB."
        )
        content = InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=text
        )
        await callback.message.edit_media(
            media=content,
            reply_markup=back_profile_kb()
        )
        logger.info(f"Payment successful for tg_id={tg_id}, invoice_id={invoice_id}, amount={transaction.amount}")
        await state.clear()
        await callback.answer()
    else:
        status_map = {
            "NEW": "новый (ожидает оплаты)",
            "PROCESS": "в обработке",
            "UNDERPAID": "оплачен не полностью",
            "OVERPAID": "оплачен больше суммы",
            "FAIL": "неуспешный"
        }
        human_status = status_map.get(invoice_status, invoice_status)

        await callback.answer(
            text=f"⚠️ Оплата не завершена. Статус: {human_status}. Попробуйте ещё раз через несколько минут.",
            show_alert=True
        )
