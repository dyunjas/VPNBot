from aiogram.utils.keyboard import InlineKeyboardBuilder


def information_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="Поддержка", url="https://t.me/LunetVPNSupport", icon_custom_emoji_id="5906995262378741881", style="danger")
    builder.button(text="Канал", url="https://t.me/LunetVpn", icon_custom_emoji_id="5771695636411847302", style="primary")
    builder.button(text="Оферта", url="https://lunet.pro/terms/offer/", icon_custom_emoji_id="5877597667231534929", style="primary")
    builder.button(text="Политика конфиденциальности", url="https://lunet.pro/terms/privacy/", icon_custom_emoji_id="5877597667231534929", style="primary")
    builder.button(text="Пользовательское соглашение", url="https://lunet.pro/terms/", icon_custom_emoji_id="5877597667231534929", style="primary")
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()
