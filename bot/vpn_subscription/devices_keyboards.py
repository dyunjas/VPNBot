from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

DEVICES_PER_PAGE = 6


def devices_list_kb(devices: list, page: int = 0):
    builder = InlineKeyboardBuilder()

    start = page * DEVICES_PER_PAGE
    end = start + DEVICES_PER_PAGE
    chunk = devices[start:end]

    for idx, dev in enumerate(chunk, start=start):
        title = dev.get("deviceModel") or dev.get("platform") or f"Устройство #{idx + 1}"
        builder.button(
            text=f"📱 {title}",
            callback_data=f"subscription_device:{idx}:{page}",
        )

    builder.adjust(1)

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"subscription_devices_page:{page - 1}"))
    if end < len(devices):
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"subscription_devices_page:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ К подписке", callback_data="vpn_subscription"))
    return builder.as_markup()


def device_detail_kb(device_id: int, page: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить", callback_data=f"subscription_device_delete:{device_id}:{page}")
    builder.button(text="⬅️ Назад", callback_data=f"subscription_devices_page:{page}")
    builder.adjust(1)
    return builder.as_markup()
