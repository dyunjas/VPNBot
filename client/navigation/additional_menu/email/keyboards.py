from aiogram.utils.keyboard import InlineKeyboardBuilder

def back_profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="profile")

    builder.adjust(1)
    return builder.as_markup()