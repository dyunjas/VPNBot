from aiogram.utils.keyboard import InlineKeyboardBuilder


def email_bind_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()

def email_bind_cancel_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="Отмена", callback_data="main_menu", icon_custom_emoji_id="5778527486270770928", style="danger")
    builder.adjust(1)
    return builder.as_markup()
