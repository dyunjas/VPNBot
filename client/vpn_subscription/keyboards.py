from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def back_keys_kb(url):
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="Копировать ссылку", copy_text={"text": f"{url}"}))
    builder.button(text="🔄 Перевыпустить ключи", callback_data="reissue_keys")
    builder.button(text="⬅️ Назад", callback_data="main_menu")

    builder.adjust(1)
    return builder.as_markup()