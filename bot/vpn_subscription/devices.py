from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.core.logger_config import logger
from backend.images import MAIN_MENU_IMG
from backend.services import RemnaWaveService, UserService
from backend.services.exceptions import UserNotFound
from bot.vpn_subscription.devices_keyboards import device_detail_kb, devices_list_kb

router = Router()


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        txt = value.strip()
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


async def _render_devices_page(callback: CallbackQuery, devices: list[dict], page: int):
    if not devices:
        text = (
            "<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> <b>Устройства не найдены</b>\n\n"
            "Подписка ещё не использовалась на устройствах."
        )
        media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
        await callback.message.edit_media(media=media, reply_markup=devices_list_kb([], 0))
        return

    max_page = max((len(devices) - 1) // 6, 0)
    page = min(max(page, 0), max_page)

    text = (
        "<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> <b>Ваши устройства</b>\n\n"
        "Выберите устройство, чтобы посмотреть детали или удалить его."
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=devices_list_kb(devices, page))


@router.callback_query(F.data == "subscription_devices")
async def subscription_devices(
    callback: CallbackQuery,
    user_service: UserService,
    remnawave_service: RemnaWaveService,
):
    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    if not remnawave_service.enabled:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    devices = await remnawave_service.get_user_hwid_devices(user=user)
    await _render_devices_page(callback, devices, 0)
    await callback.answer()


@router.callback_query(F.data.startswith("subscription_devices_page:"))
async def subscription_devices_page(
    callback: CallbackQuery,
    user_service: UserService,
    remnawave_service: RemnaWaveService,
):
    try:
        page = int(callback.data.split(":", 1)[1])
    except Exception:
        page = 0

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    if not remnawave_service.enabled:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    devices = await remnawave_service.get_user_hwid_devices(user=user)
    await _render_devices_page(callback, devices, page)
    await callback.answer()


@router.callback_query(F.data.startswith("subscription_device:"))
async def subscription_device_detail(
    callback: CallbackQuery,
    user_service: UserService,
    remnawave_service: RemnaWaveService,
):
    try:
        _, device_index_str, page_str = callback.data.split(":")
        device_index = int(device_index_str)
        page = int(page_str)
    except Exception:
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    if not remnawave_service.enabled:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    devices = await remnawave_service.get_user_hwid_devices(user=user)
    if device_index < 0 or device_index >= len(devices):
        await callback.answer("Устройство не найдено.", show_alert=True)
        return

    device = devices[device_index]
    text = (
        "<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> <b>Информация об устройстве</b>\n\n"
        f"<b>HWID:</b> <code>{device.get('hwid') or '—'}</code>\n"
        f"<b>Модель:</b> {device.get('deviceModel') or '—'}\n"
        f"<b>OS:</b> {device.get('platform') or '—'}\n"
        f"<b>Версия ОС:</b> {device.get('osVersion') or '—'}\n"
        f"<b>User-Agent:</b> {device.get('userAgent') or '—'}\n"
        f"<b>Первое подключение:</b> {_fmt_dt(_parse_iso(device.get('createdAt')))}\n"
        f"<b>Последняя активность:</b> {_fmt_dt(_parse_iso(device.get('updatedAt')))}"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=device_detail_kb(device_index, page))
    await callback.answer()


@router.callback_query(F.data.startswith("subscription_device_delete:"))
async def subscription_device_delete(
    callback: CallbackQuery,
    user_service: UserService,
    remnawave_service: RemnaWaveService,
):
    try:
        _, device_index_str, page_str = callback.data.split(":")
        device_index = int(device_index_str)
        page = int(page_str)
    except Exception:
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
        if not remnawave_service.enabled:
            await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
            return

        devices = await remnawave_service.get_user_hwid_devices(user=user)
        if device_index < 0 or device_index >= len(devices):
            await callback.answer("Устройство уже удалено.", show_alert=True)
            return

        hwid = str(devices[device_index].get("hwid") or "").strip()
        deleted_remote = await remnawave_service.delete_hwid_device(user=user, hwid=hwid)
        if not deleted_remote:
            await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
            return

        devices = await remnawave_service.get_user_hwid_devices(user=user)
        await _render_devices_page(callback, devices, page)
        await callback.answer("Устройство удалено.")
    except UserNotFound:
        await callback.answer("Пользователь не найден.", show_alert=True)
    except Exception as e:
        logger.exception("[bot][devices] delete failed user_tg_id=%s device_index=%s: %s", callback.from_user.id, device_index, e)
        await callback.answer("Ошибка удаления устройства.", show_alert=True)
