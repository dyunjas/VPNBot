from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import WebAppInfo

def main_menu_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="📄 Тарифы", callback_data="subscription")
    builder.button(text="🌙 Подписка", callback_data="vpn_subscription")
    builder.button(
        text="🚀 Мини-Приложение",
        web_app=WebAppInfo(url="https://lunetpn.ru/miniapp/")
    )
    builder.button(text="🌟 Профиль", callback_data="profile")
    builder.button(text="✨ Информация", callback_data="information")

    builder.adjust(2, 1, 2)

    return builder.as_markup()