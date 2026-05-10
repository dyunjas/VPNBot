from aiogram.utils.keyboard import InlineKeyboardBuilder

def profile_kb():
    builder =  InlineKeyboardBuilder()

    builder.button(text="🌟 Пополнить баланс", callback_data="add_funds")
    builder.button(text="🎁 Промокод", callback_data="activate_promocode")
    builder.button(text="💳 Транзакции", callback_data="transaction_history")
    builder.button(text="👥 Реферальная система", callback_data="referral")
    builder.button(text="🪐 В главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def promocode_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="⬅️ Назад", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()