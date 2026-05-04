from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

MINIAPP_URL = "https://7462-31-13-208-190.ngrok-free.app/miniapp/"


def main_menu_kb():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🚀 Веб-сайт",
        web_app=WebAppInfo(url=MINIAPP_URL),
    )
    builder.button(text="📄 Купить подписку", callback_data="subscription")
    builder.button(text="🌙 Моя подписка", callback_data="vpn_subscription")
    builder.button(text="🌟 Профиль", callback_data="profile")
    builder.button(text="✨ О сервисе", callback_data="information")

    builder.adjust(1)
    return builder.as_markup()
