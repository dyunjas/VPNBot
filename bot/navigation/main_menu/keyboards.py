import os
from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

MINIAPP_URL = os.getenv("MINIAPP_URL", "https://miniapp.lunetpn.ru/miniapp/")




def main_menu_kb():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Веб-сайт",
        web_app=WebAppInfo(url=MINIAPP_URL), icon_custom_emoji_id="5884343982816759327", style="primary"
    )
    builder.button(text="Купить подписку", callback_data="subscription", icon_custom_emoji_id="5967456680940671207", style="primary")
    builder.button(text="Моя подписка", callback_data="vpn_subscription", icon_custom_emoji_id="6005570495603282482", style="primary")
    builder.button(text="Баланс", callback_data="balance_menu", icon_custom_emoji_id="5769403330761593044", style="success")
    builder.button(text="Пригласить", callback_data="referral", icon_custom_emoji_id="5942877472163892475", style="primary")
    builder.button(text="Почта", callback_data="email_bind", icon_custom_emoji_id="5967280668885913944", style="primary")
    builder.button(text="О сервисе", callback_data="information", icon_custom_emoji_id="5987661379627128559", style="primary")

    builder.adjust(1, 1, 1, 1, 2, 1)
    return builder.as_markup()

