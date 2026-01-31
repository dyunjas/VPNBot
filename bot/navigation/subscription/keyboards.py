from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

PLANS_PER_PAGE = 4


def subscription_plans_kb(plans, page: int = 0):
    builder = InlineKeyboardBuilder()

    start = page * PLANS_PER_PAGE
    end = start + PLANS_PER_PAGE
    chunk = plans[start:end]

    for plan in chunk:
        builder.button(
            text=f"{plan.name}",
            callback_data=f"plan:{plan.id}:{page}"
        )
    
    builder.adjust(2)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"plans_page:{page-1}")
        )
    if end < len(plans):
        nav_buttons.append(
            InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"plans_page:{page+1}")
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🪐 В главное меню", callback_data="main_menu"))

    return builder.as_markup()

def purchase_subscription_plan(plan_id: int, page: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить", callback_data=f"purchase_plan:{plan_id}")
    builder.button(text="⬅️ К планам", callback_data=f"plans_page:{page}")
    builder.adjust(1)
    return builder.as_markup()