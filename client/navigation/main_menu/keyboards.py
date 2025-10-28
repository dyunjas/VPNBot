from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="🌙 Подписка", callback_data="my_subscription")
    builder.button(text="🔑 Мои ключи", callback_data="my_keys")
    builder.button(text="🌟 Профиль", callback_data="profile")
    builder.button(text="✨ Информация", callback_data="information")
    builder.adjust(2, 2)
    return builder.as_markup()