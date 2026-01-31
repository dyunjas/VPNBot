from aiogram.utils.keyboard import InlineKeyboardBuilder

def information_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="💬 Канал", url="https://t.me/LunetVpn")
    builder.button(text="🚀 FAQ", url="https://telegra.ph/Polzovatelskoe-soglashenie-LunetVPN-LunetVpnBot-10-27")
    builder.button(text="🚨 Поддержка", url="https://t.me/LunetVPNSupportBot")
    builder.button(text="🪐 Главное меню", callback_data="main_menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()