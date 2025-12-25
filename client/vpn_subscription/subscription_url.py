from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from server.core.loader import settings
from server.repositories.user_repository import UserRepository
from server.repositories.subscription_repository import SubscriptionRepository
from server.repositories.server_repository import ServerRepository
from server.repositories.key_repository import KeyRepository
from server.database.models import KeyStatus

from datetime import datetime
from server.core.logger_config import logger
from server.images import MAIN_MENU_IMG

from client.vpn_subscription.keyboards import back_keys_kb

router = Router()
XRAY_AUTH_TOKEN = settings.XRAY_AUTH


@router.callback_query(F.data == "vpn_subscription")
async def subscription_link(
    callback: CallbackQuery,
    user_repo: UserRepository,
    subscription_repo: SubscriptionRepository,
    server_repo: ServerRepository,
    key_repo: KeyRepository,
):
    tg_id = callback.from_user.id

    user = await user_repo.get_user_by_tg_id(tg_id)
    if not user:
        user = await user_repo.create_user(
            tg_id=tg_id,
            username=callback.from_user.username,
        )

    subscription = await subscription_repo.get_active_subscription_with_plan_by_tg(tg_id)
    if not subscription or subscription.current_period_end <= datetime.now():
        text = "⚠️ У вас нет активной подписки.\nОформите подписку, чтобы получить ссылку на подписку."
        await callback.answer(
            text=text,
            show_alert=True
        )
        await callback.answer()
        return

    if user.subscription_token:
        url = f"https://{settings.PUBLIC_BASE_URL}/sub/{user.subscription_token}"
        text = (
            "🔗 <b>Ваша VPN ссылка:</b>\n"
            f"<code>{url}</code>\n\n"
            f"✨ Активна до: <b>{subscription.current_period_end:%d.%m.%Y %H:%M}</b>\n\n"
            "ℹ️ Серверы уже подготовлены. Вы можете обновить подписку в приложение.\n\n"
            '<a href="https://telegra.ph/Lunet-VPN---instrukciya-12-18"><b>📝 Инструкция по подключению(нажмите, чтобы перейти)</b></a>'
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
        return

    text = (
        "⏳ <b>Создаю ключи...</b>\n\n"
        "Пожалуйста, подождите до 60 секунд."
        )
    media = InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=text,
            parse_mode="HTML"
        )
    status_msg = await callback.message.edit_media(
        media=media,
    )
    await callback.answer()

    token = await user_repo.get_or_create_subscription_token(tg_id)

    keys = await key_repo.get_keys_by_user_id(user.id)
    active_keys = [k for k in keys if k.status == KeyStatus.active]
    keys_by_server = {k.server_id: k for k in active_keys}

    servers = await server_repo.get_all_servers()
    created = 0

    for server in servers:
        if server.id in keys_by_server:
            continue

        try:
            key = await key_repo.create_key(
                user_id=user.id,
                server=server,
                auth_token=XRAY_AUTH_TOKEN,
                label=server.country,
            )
            keys_by_server[server.id] = key
            created += 1
        except Exception as e:
            logger.error(
                f"[sub_url] create_key failed user_id={user.id} server_id={server.id}: {e}"
            )

    url = f"https://{settings.PUBLIC_BASE_URL}/sub/{token}"

    text = (
        "✅ <b>Ключи готовы!</b>\n\n"
        "🔗 Ваша ссылка подписки (вставьте в V2RayTun):\n"
        f"<code>{url}</code>\n\n"
        f"📊 Серверов доступно: <b>{len(keys_by_server)}</b>\n"
        f"🆕 Создано новых ключей: <b>{created}</b>"
        )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        )
    await status_msg.edit_media(
        media=media,
        reply_markup=back_keys_kb(url),
        disable_web_page_preview=True
    )
