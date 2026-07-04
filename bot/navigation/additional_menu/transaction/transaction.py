from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG

from bot.navigation.additional_menu.transaction.keyboards import (
    back_to_profile_kb,
    build_transactions_kb, back_to_transactions_bt
)

router = Router()


@router.callback_query(F.data == "transaction_history")
async def transactions_clb(callback: CallbackQuery, bot_api):
    txs = await bot_api.list_transactions(tg_id=callback.from_user.id)

    if not txs:
        content = InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption="У вас пока нет транзакций"
        )
        await callback.message.edit_media(
            media=content,
            reply_markup=back_to_profile_kb()
        )
        await callback.answer()
        return

    keyboard = build_transactions_kb(txs, page=0)
    content = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption="Ваши транзакции:"
    )
    await callback.message.edit_media(
        media=content,
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("transactions_page:"))
async def transaction_orders_clb(callback: CallbackQuery, bot_api):
    page = int(callback.data.split(":")[1])
    txs = await bot_api.list_transactions(tg_id=callback.from_user.id)

    if not txs:
        content = InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption="У вас пока нет транзакций"
        )
        await callback.message.edit_media(
            media=content,
            reply_markup=back_to_profile_kb()
        )
        await callback.answer()
        return

    keyboard = build_transactions_kb(txs, page=page)
    content = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption="Ваши транзакции:"
    )
    await callback.message.edit_media(
        media=content,
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("transaction:"))
async def transaction_detail_clb(callback: CallbackQuery, bot_api):
    parts = callback.data.split(":")
    transaction_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    try:
        tx = await bot_api.get_transaction(tg_id=callback.from_user.id, transaction_id=transaction_id)
        transaction = tx.get("transaction") if isinstance(tx, dict) else tx
    except Exception:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Транзакция не найдена"
        )
        return

    created_at_text = transaction.get("created_at") or "-"
    paid_at_text = transaction.get("paid_at") or "-"
    status_text = "Оплачено" if transaction.get("paid") else "Не оплачено"

    text = (
        f"<b><tg-emoji emoji-id='5769403330761593044'>👝</tg-emoji> Сумма:</b> {transaction.get('amount')} RUB\n"
        f"<b><tg-emoji emoji-id='5900104897885376843'>🕓</tg-emoji> Дата создания:</b> {created_at_text}\n"
        f"<b><tg-emoji emoji-id='5900104897885376843'>🕓</tg-emoji> Дата оплаты:</b> {paid_at_text}\n"
        f"<b><tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Статус:</b> {status_text}\n"
        f"<b><tg-emoji emoji-id='5983399041197675256'>🏪</tg-emoji> Система:</b> {transaction.get('payment_system')}\n"
        f"<b><tg-emoji emoji-id='5985433648810171091'>🏷</tg-emoji> ID транзакции:</b> <code>{transaction.get('transaction_id')}</code>"
    )

    content = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=content,
        reply_markup=back_to_transactions_bt(page)
    )
    await callback.answer()

