from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

MINIAPP_URL = "https://6ecf-194-116-236-249.ngrok-free.app/miniapp/?v=401"


def main_menu_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="📄 Тарифы", callback_data="subscription")
    builder.button(text="🌙 Подписка", callback_data="vpn_subscription")
    builder.button(
        text="🚀 Мини-Приложение",
        web_app=WebAppInfo(url=MINIAPP_URL),
    )
    builder.button(text="🌟 Профиль", callback_data="profile")
    builder.button(text="✨ Информация", callback_data="information")

    builder.adjust(2, 1, 2)
    return builder.as_markup()
