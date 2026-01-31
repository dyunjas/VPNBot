from aiogram.utils.keyboard import InlineKeyboardBuilder

def fail_purchase_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="💳 Пополнить баланс", callback_data="add_funds")
    builder.button(text="🪐 В главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def success_purchase_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="🔄 VPN ссылка", callback_data="vpn_subscription")
    builder.button(text="🪐 В главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()