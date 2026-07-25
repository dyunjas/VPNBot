from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

DEVICES_PER_PAGE = 6
ANDROID_EMOJI_ID = "5819078828017849357"
APPLE_EMOJI_ID = "5818920837645867167"
WINDOWS_EMOJI_ID = "5818956713507689486"
OTHER_DEVICE_EMOJI_ID = "5967816500415827773"


def _device_title(dev: dict, index: int) -> str:
    model = (dev.get("device_model") or dev.get("deviceModel") or "").strip()
    platform = (dev.get("device_os") or dev.get("platform") or "").strip()
    hwid = (dev.get("hwid") or "").strip()

    title = model or platform or hwid or f"Устройство {index + 1}"
    return title[:40]


def _device_emoji_id(dev: dict) -> str:
    platform = str(dev.get("device_os") or dev.get("platform") or "").strip().lower()
    user_agent = str(dev.get("user_agent") or dev.get("userAgent") or "").strip().lower()
    raw = f"{platform} {user_agent}"

    if "android" in raw:
        return ANDROID_EMOJI_ID
    if any(value in raw for value in ("apple", "ios", "iphone", "ipad", "macos", "mac os", "darwin")):
        return APPLE_EMOJI_ID
    if "windows" in raw:
        return WINDOWS_EMOJI_ID
    return OTHER_DEVICE_EMOJI_ID


def devices_list_kb(devices: list, page: int = 0):
    builder = InlineKeyboardBuilder()

    start = page * DEVICES_PER_PAGE
    end = start + DEVICES_PER_PAGE
    chunk = devices[start:end]

    for idx, dev in enumerate(chunk, start=start):
        builder.button(
            text=_device_title(dev, idx),
            callback_data=f"subscription_device:{idx}:{page}",
            icon_custom_emoji_id=_device_emoji_id(dev),
            style="primary",
        )

    builder.adjust(1)

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Назад",
                callback_data=f"subscription_devices_page:{page - 1}",
                icon_custom_emoji_id="5877536313623711363",
                style="primary",
            )
        )
    if end < len(devices):
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд",
                callback_data=f"subscription_devices_page:{page + 1}",
                icon_custom_emoji_id="5875506366050734240",
                style="primary",
            )
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(
            text="К подписке",
            callback_data="vpn_subscription",
            icon_custom_emoji_id="5877536313623711363",
            style="primary",
        )
    )
    return builder.as_markup()


def device_detail_kb(device_id: int, page: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить", callback_data=f"subscription_device_delete:{device_id}:{page}", icon_custom_emoji_id="5841541824803509441", style="danger")
    builder.button(text="Назад", callback_data=f"subscription_devices_page:{page}", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()
