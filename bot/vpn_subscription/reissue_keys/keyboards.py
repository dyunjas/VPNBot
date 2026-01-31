from aiogram.utils.keyboard import InlineKeyboardBuilder

def reissue_keys_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_reissue_keys")
    builder.button(text="⬅️ Назад", callback_data="vpn_subscription")

    builder.adjust(1)
    return builder.as_markup()