from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import SUBSCRIPTION_IMG
from bot.vpn_subscription.devices_keyboards import device_detail_kb, devices_list_kb

router = Router()


async def _safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest:
        return


def _device_title(device: dict, device_id: int) -> str:
    return (
        device.get("device_model")
        or device.get("deviceModel")
        or device.get("device_os")
        or device.get("platform")
        or f"Устройство {device_id + 1}"
    )


def _render_devices_text(devices: list[dict]) -> str:
    if not devices:
        return "У вас пока нет устройств."
    return "Выберите устройство для просмотра или удаления."


def _render_device_detail(device: dict, device_id: int) -> str:
    hwid = device.get("hwid") or "—"
    model = device.get("device_model") or device.get("deviceModel") or "—"
    platform = device.get("device_os") or device.get("platform") or "—"
    os_version = device.get("os_version") or device.get("osVersion") or "—"
    user_agent = device.get("user_agent") or device.get("userAgent") or "—"
    return (
        f"<b>{_device_title(device, device_id)}</b>\n\n"
        f"<b>Модель:</b> {model}\n"
        f"<b>Платформа:</b> {platform}\n"
        f"<b>Версия ОС:</b> {os_version}\n"
        f"<b>User-Agent:</b> {user_agent}\n"
        f"<b>HWID:</b>\n<code>{hwid}</code>"
    )


async def _load_devices(bot_api, tg_id: int) -> list[dict]:
    return await bot_api.get_devices(tg_id=tg_id)


async def _render_list(callback: CallbackQuery, bot_api, *, page: int = 0) -> None:
    devices = await _load_devices(bot_api, callback.from_user.id)
    content = InputMediaPhoto(
        media=SUBSCRIPTION_IMG,
        caption=_render_devices_text(devices),
    )
    await callback.message.edit_media(
        media=content,
        reply_markup=devices_list_kb(devices, page),
    )


@router.callback_query(F.data == "subscription_devices")
async def devices_clb(callback: CallbackQuery, bot_api):
    try:
        await _render_list(callback, bot_api, page=0)
    except Exception:
        await _safe_callback_answer(callback, "Не удалось получить список устройств", show_alert=True)
        return
    await _safe_callback_answer(callback)


@router.callback_query(F.data.startswith("subscription_devices_page:"))
async def devices_page_clb(callback: CallbackQuery, bot_api):
    try:
        page = int(callback.data.split(":", 1)[1])
    except ValueError:
        await _safe_callback_answer(callback, "Неверная страница", show_alert=True)
        return

    try:
        await _render_list(callback, bot_api, page=page)
    except Exception:
        await _safe_callback_answer(callback, "Не удалось получить список устройств", show_alert=True)
        return
    await _safe_callback_answer(callback)


@router.callback_query(F.data.startswith("subscription_device:"))
async def device_detail_clb(callback: CallbackQuery, bot_api):
    try:
        _, device_id_str, page_str = callback.data.split(":")
        device_id = int(device_id_str)
        page = int(page_str)
    except ValueError:
        await _safe_callback_answer(callback, "Неверный идентификатор устройства", show_alert=True)
        return

    devices = await _load_devices(bot_api, callback.from_user.id)
    if device_id < 0 or device_id >= len(devices):
        await _safe_callback_answer(callback, "Устройство не найдено", show_alert=True)
        return

    device = devices[device_id]
    content = InputMediaPhoto(
        media=SUBSCRIPTION_IMG,
        caption=_render_device_detail(device, device_id),
        parse_mode="HTML",
    )
    await callback.message.edit_media(
        media=content,
        reply_markup=device_detail_kb(device_id, page),
    )
    await _safe_callback_answer(callback)


@router.callback_query(F.data.startswith("subscription_device_delete:"))
async def device_delete_clb(callback: CallbackQuery, bot_api):
    try:
        _, device_id_str, page_str = callback.data.split(":")
        device_id = int(device_id_str)
        page = int(page_str)
    except ValueError:
        await _safe_callback_answer(callback, "Неверный идентификатор устройства", show_alert=True)
        return

    try:
        await bot_api.delete_device(tg_id=callback.from_user.id, device_id=device_id)
    except Exception:
        await _safe_callback_answer(callback, "Не удалось удалить устройство", show_alert=True)
        return

    try:
        await _render_list(callback, bot_api, page=page)
    except Exception:
        await _safe_callback_answer(callback, "Не удалось получить список устройств", show_alert=True)
        return
    await _safe_callback_answer(callback, "Устройство удалено")
