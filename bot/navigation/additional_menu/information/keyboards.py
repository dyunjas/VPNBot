from aiogram.utils.keyboard import InlineKeyboardBuilder


def information_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="💬 Канал", url="https://t.me/LunetVpn")
    builder.button(text="🚀 Оферта", url="https://lunetpn.ru/terms/offer/")
    builder.button(text="🔐 Политика конфиденциальности", url="https://lunetpn.ru/terms/privacy/")
    builder.button(text="💼 Пользовательское соглашение", url="https://lunetpn.ru/terms/")
    builder.button(text="🚨 Поддержка", url="https://t.me/LunetVPNSupport")
    builder.button(text="🪐 Главное меню", callback_data="main_menu")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()
