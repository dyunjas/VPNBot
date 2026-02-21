from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG
from backend.services import DeviceService, UserService
from backend.services.exceptions import DeviceNotFound, UserNotFound
from bot.vpn_subscription.devices_keyboards import device_detail_kb, devices_list_kb

router = Router()


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")


async def _render_devices_page(callback: CallbackQuery, user_id: int, page: int, device_service: DeviceService):
    devices = await device_service.list_devices(user_id)

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
    device_service: DeviceService,
):
    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await _render_devices_page(callback, user.id, 0, device_service)
    await callback.answer()


@router.callback_query(F.data.startswith("subscription_devices_page:"))
async def subscription_devices_page(
    callback: CallbackQuery,
    user_service: UserService,
    device_service: DeviceService,
):
    try:
        page = int(callback.data.split(":", 1)[1])
    except Exception:
        page = 0

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await _render_devices_page(callback, user.id, page, device_service)
    await callback.answer()


@router.callback_query(F.data.startswith("subscription_device:"))
async def subscription_device_detail(
    callback: CallbackQuery,
    user_service: UserService,
    device_service: DeviceService,
):
    try:
        _, device_id_str, page_str = callback.data.split(":")
        device_id = int(device_id_str)
        page = int(page_str)
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
        device = await device_service.get_device_by_id(user_id=user.id, device_id=device_id)
    except (UserNotFound, DeviceNotFound):
        await callback.answer("Устройство не найдено", show_alert=True)
        return

    text = (
        "<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> <b>Информация об устройстве</b>\n\n"
        f"<b>ID:</b> <code>{device.id}</code>\n"
        f"<b>HWID:</b> <code>{device.hwid}</code>\n"
        f"<b>Модель:</b> {device.device_model or '—'}\n"
        f"<b>OS:</b> {device.device_os or '—'}\n"
        f"<b>Версия ОС:</b> {device.os_version or '—'}\n"
        f"<b>Язык:</b> {device.device_locale or '—'}\n"
        f"<b>Первое подключение:</b> {_fmt_dt(device.first_seen_at)}\n"
        f"<b>Последняя активность:</b> {_fmt_dt(device.last_seen_at)}"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=device_detail_kb(device.id, page))
    await callback.answer()


@router.callback_query(F.data.startswith("subscription_device_delete:"))
async def subscription_device_delete(
    callback: CallbackQuery,
    user_service: UserService,
    device_service: DeviceService,
):
    try:
        _, device_id_str, page_str = callback.data.split(":")
        device_id = int(device_id_str)
        page = int(page_str)
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
        await device_service.remove_device_for_user(user_id=user.id, device_id=device_id)
    except UserNotFound:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    except DeviceNotFound:
        await callback.answer("Устройство уже удалено", show_alert=True)
        return

    await _render_devices_page(callback, user.id, page, device_service)
    await callback.answer("Устройство удалено")
