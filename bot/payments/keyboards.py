from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()


def payment_choice_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="СБП 1", callback_data="pay_pally", icon_custom_emoji_id="5987917196469213507", style="success")
    builder.button(text="СБП 2", callback_data="pay_platega:sbp", icon_custom_emoji_id="5987917196469213507", style="success")
    builder.button(text="Банковская карта", callback_data="pay_platega:card", icon_custom_emoji_id="5927169041595634481", style="success")
    builder.button(text="Криптовалюта", callback_data="pay_cryptobot", icon_custom_emoji_id="5963312935148195483", style="success")
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()


def payment_menu_kb(invoice_url: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить", url=invoice_url, icon_custom_emoji_id="5884343982816759327", style="success")
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()
