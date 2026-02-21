from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.core.config import settings
from backend.images import MAIN_MENU_IMG
from backend.services import SubscriptionService, UserService
from backend.services.exceptions import SubscriptionNotFound, UserNotFound
from bot.vpn_subscription.keyboards import back_keys_kb

router = Router()


def _as_aware_utc(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.callback_query(F.data == "vpn_subscription")
async def subscription_link(
    callback: CallbackQuery,
    user_service: UserService,
    subscription_service: SubscriptionService,
):
    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id=tg_id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Перезапустите бота."
        )
        return

    try:
        subscription = await subscription_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        await callback.answer(
            "У вас нет активной подписки. Оформите подписку, чтобы получить ссылку.",
            show_alert=True,
        )
        return

    end_dt = _as_aware_utc(subscription.current_period_end)
    now = datetime.now(timezone.utc)
    if not end_dt or end_dt <= now:
        await callback.answer(
            "У вас нет активной подписки. Оформите подписку, чтобы получить ссылку.",
            show_alert=True,
        )
        return

    try:
        subscription_token = await user_service.get_subscription_token(user_id=user.id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Перезапустите бота."
        )
        return

    url = f"https://{settings.PUBLIC_BASE_URL}/sub/{subscription_token}"

    devices_limit = int(getattr(subscription, "devices_limit", 0) or 0)
    devices_left = int(getattr(subscription, "devices_left", 0) or 0)
    devices_used = max(devices_limit - devices_left, 0)

    text = (
        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> <b>Ваша VPN ссылка:</b>\n"
        f"<code>{url}</code>\n\n"
        f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Активна до: <b>{end_dt:%d.%m.%Y %H:%M}</b>\n"
        f"<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Устройства: <b>{devices_used}/{devices_limit}</b>\n\n"
        "<tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Серверы уже подготовлены. Обновите подписку в приложении.\n\n"
        "<tg-emoji emoji-id='5877318502947229960'>💻</tg-emoji>"
        "<a href='https://telegra.ph/Lunet-VPN---instrukciya-12-18'><b>Инструкция по подключению (нажмите, чтобы перейти)</b></a>"
    )

    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(
        media=media,
        reply_markup=back_keys_kb(url),
        disable_web_page_preview=True,
    )
    await callback.answer()
