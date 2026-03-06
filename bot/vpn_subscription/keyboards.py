from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_keys_kb(url: str, auto_renew: bool = False):
    builder = InlineKeyboardBuilder()
    auto_text = "🟢 Автопродление: ВКЛ" if auto_renew else "🔴 Автопродление: ВЫКЛ"

    builder.add(InlineKeyboardButton(text="Копировать ссылку", copy_text={"text": url}))
    builder.button(text=auto_text, callback_data="toggle_auto_renew")
    builder.button(text="➕ Докупить трафик", callback_data="buy_extra_traffic")
    builder.button(text="♻️ Перевыпустить VPN-ссылку", callback_data="reissue_subscription_url")
    builder.button(text="🔄 Перевыпустить ключи", callback_data="reissue_keys")
    builder.button(text="📱 Устройства", callback_data="subscription_devices")
    builder.button(text="⬅️ Назад", callback_data="main_menu")

    builder.adjust(1)
    return builder.as_markup()


def reissue_subscription_url_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_reissue_subscription_url")
    builder.button(text="⬅️ Назад", callback_data="vpn_subscription")
    builder.adjust(1)
    return builder.as_markup()
