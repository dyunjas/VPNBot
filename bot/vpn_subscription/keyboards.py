from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_keys_kb(url: str | None, auto_renew: bool = False):
    builder = InlineKeyboardBuilder()
    auto_text = "Автопродление: да" if auto_renew else "Автопродление: нет"

    if url:
        builder.button(text="Копировать ссылку", copy_text={"text": url}, style="primary")
    builder.button(text=auto_text, callback_data="toggle_auto_renew", icon_custom_emoji_id="6005843436479975944", style="primary")
    builder.button(text="Купить гигабайты", callback_data="reset_traffic", icon_custom_emoji_id="5927169041595634481", style="primary")
    builder.button(text="Устройства", callback_data="subscription_devices", icon_custom_emoji_id="5877318502947229960", style="primary")
    builder.button(text="Назад", callback_data="main_menu", icon_custom_emoji_id="5877536313623711363", style="primary")

    builder.adjust(1)
    return builder.as_markup()
