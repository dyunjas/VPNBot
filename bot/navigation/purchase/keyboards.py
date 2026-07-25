from aiogram.utils.keyboard import InlineKeyboardBuilder

def fail_purchase_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="Пополнить баланс", callback_data="add_funds", icon_custom_emoji_id="5769403330761593044", style="success")
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()

def success_purchase_kb():
    builder = InlineKeyboardBuilder()

    builder.button(text="Моя подписка", callback_data="vpn_subscription", icon_custom_emoji_id="6005570495603282482", style="primary")
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()
