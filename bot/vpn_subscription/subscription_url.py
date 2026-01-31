from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.core.config import settings
from backend.database.models import KeyStatus
from backend.services import (
    UserService, SubscriptionService,
    VPNService
)
from backend.services.exceptions import UserNotFound

from datetime import datetime
from backend.core.logger_config import logger
from backend.images import MAIN_MENU_IMG

from bot.vpn_subscription.keyboards import back_keys_kb

router = Router()
XRAY_AUTH_TOKEN = settings.XRAY_AUTH


@router.callback_query(F.data == "vpn_subscription")
async def subscription_link(
    callback: CallbackQuery,
    user_service: UserService,
    subscription_service: SubscriptionService
):
    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id=tg_id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    try:
        subscription = await subscription_service.get_active_subscription(user_id=user.id)
    except UserNotFound:
        await callback.message.answer

    if not subscription or subscription.current_period_end <= datetime.now():
        await callback.answer(
            text="У вас нет активной подписки.\nОформите подписку, чтобы получить ссылку на подписку.",
            show_alert=True
        )
        return

    try:
        subscription_token = await user_service.get_subscription_token(user_id=user.id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return
    
    url = f"https://{settings.PUBLIC_BASE_URL}/sub/{subscription_token}"

    inst_emoji = "<tg-emoji emoji-id='5877318502947229960'>💻</tg-emoji>"
    text = (
            "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> <b>Ваша VPN ссылка:</b>\n"
            f"<code>{url}</code>\n\n"
            f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Активна до: <b>{subscription.current_period_end:%d.%m.%Y %H:%M}</b>\n\n"
            "<tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Серверы уже подготовлены. Вы можете обновить подписку в приложение.\n\n"
            "<tg-emoji emoji-id='5877318502947229960'>💻</tg-emoji>"
            f'<a href="https://telegra.ph/Lunet-VPN---instrukciya-12-18"><b>Инструкция по подключению(нажмите, чтобы перейти)</b></a>'
        )
    media = InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=text,
            parse_mode="HTML"
        )
    await callback.message.edit_media(
            media=media,
            reply_markup=back_keys_kb(url),
            disable_web_page_preview=True,
        )
    await callback.answer()