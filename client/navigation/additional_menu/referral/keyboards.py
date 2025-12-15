from aiogram.utils.keyboard import InlineKeyboardBuilder

def referral_kb(share_link_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Поделиться", url=share_link_url)
    builder.button(text="⬅️ Назад", callback_data="profile")

    builder.adjust(1, 1)
    return builder.as_markup()