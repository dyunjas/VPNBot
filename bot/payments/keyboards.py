from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()


def payment_choice_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡️ СБП 1", callback_data="pay_pally")
    builder.button(text="⚡️ СБП 2", callback_data="pay_platega:sbp")
    builder.button(text="💳 Банковская карта", callback_data="pay_platega:card")
    builder.button(text="🪙 Криптовалюта", callback_data="pay_cryptobot")
    builder.button(text="⬅️ Назад", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()


def payment_menu_kb(invoice_url: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить", url=invoice_url)
    builder.adjust(1)
    return builder.as_markup()
