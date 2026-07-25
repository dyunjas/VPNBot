from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

TRANSACTIONS_PER_PAGE = 5


def build_transactions_kb(transactions, page: int = 0):
    builder = InlineKeyboardBuilder()

    start = page * TRANSACTIONS_PER_PAGE
    end = start + TRANSACTIONS_PER_PAGE
    chunk = transactions[start:end]

    for transaction in chunk:
        amount = transaction.get("amount") if isinstance(transaction, dict) else transaction.amount
        tx_id = transaction.get("id") if isinstance(transaction, dict) else transaction.id
        builder.button(text=f"💵 {amount} RUB", callback_data=f"transaction:{tx_id}:{page}")
    builder.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"transactions_page:{page-1}"))
    if end < len(transactions):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"transactions_page:{page+1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu"))

    return builder


def back_to_transactions_bt(page):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=f"transactions_page:{page}")
    builder.adjust(1)
    return builder.as_markup()


def back_to_profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()
