from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_keys_kb(url: str):
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="Копировать ссылку", copy_text={"text": url}))
    builder.button(text="🔄 Перевыпустить ключи", callback_data="reissue_keys")
    builder.button(text="📱 Устройства", callback_data="subscription_devices")
    builder.button(text="⬅️ Назад", callback_data="main_menu")

    builder.adjust(1)
    return builder.as_markup()
