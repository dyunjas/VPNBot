from aiogram.utils.keyboard import InlineKeyboardBuilder


def balance_menu_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="Пополнить баланс", callback_data="add_funds", icon_custom_emoji_id="5769403330761593044", style="success")
    builder.button(text="Промокод", callback_data="activate_promocode", icon_custom_emoji_id="5875180111744995604", style="primary")
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()


def promocode_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="Отмена", callback_data="balance_menu", icon_custom_emoji_id="5778527486270770928", style="danger")
    builder.adjust(1)
    return builder.as_markup()
