from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PLANS_PER_PAGE = 4


def subscription_plans_kb(plans, page: int = 0):
    builder = InlineKeyboardBuilder()

    start = page * PLANS_PER_PAGE
    end = start + PLANS_PER_PAGE
    chunk = plans[start:end]

    for plan in chunk:
        plan_name = plan.get("name") if isinstance(plan, dict) else plan.name
        plan_id = plan.get("id") if isinstance(plan, dict) else plan.id
        builder.button(text=plan_name, callback_data=f"plan:{plan_id}:{page}", icon_custom_emoji_id="5967456680940671207", style="primary")

    builder.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Назад",
                callback_data=f"plans_page:{page-1}",
                icon_custom_emoji_id="5877536313623711363",
                style="primary",
            )
        )
    if end < len(plans):
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд",
                callback_data=f"plans_page:{page+1}",
                icon_custom_emoji_id="5875506366050734240",
                style="primary",
            )
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(
            text="Назад",
            callback_data="main_menu",
            icon_custom_emoji_id="5877536313623711363",
            style="primary",
        )
    )
    return builder.as_markup()


def purchase_subscription_plan(plan_id: int, page: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить", callback_data=f"purchase_plan:{plan_id}", icon_custom_emoji_id="5769403330761593044", style="success")
    builder.button(text="Подарить", callback_data=f"gift_plan:{plan_id}:{page}", icon_custom_emoji_id="5956148757899776734", style="primary")
    builder.button(text="К тарифам", callback_data=f"plans_page:{page}", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()
