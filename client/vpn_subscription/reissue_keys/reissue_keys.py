from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from client.vpn_subscription.reissue_keys.keyboards import reissue_keys_kb
from client.vpn_subscription.keyboards import back_keys_kb

from server.images import MAIN_MENU_IMG
from server.repositories.user_repository import UserRepository
from server.repositories.subscription_repository import SubscriptionRepository
from server.repositories.server_repository import ServerRepository
from server.repositories.key_repository import KeyRepository
from server.core.config import settings
from server.core.logger_config import logger

from datetime import datetime

router = Router()

@router.callback_query(F.data == "reissue_keys")
async def reissue_keys_clb(callback: CallbackQuery):
    text = (
        "⚠️ Вы уверены, что хотите перевыпустить ключи?\n\n"
        "<i>ℹ️ После перевыпуска вам нужно будет обновить подписку в приложении.</i>"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=reissue_keys_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_reissue_keys")
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
        await callback.answer(text=text, show_alert=True)
        await callback.answer()
        return

    text = (
        "⏳ <b>Перевыпускаю ключи...</b>\n\n"
        "Пожалуйста, подождите до 60 секунд."
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
    )
    status_msg = await callback.message.edit_media(media=media)
    await callback.answer()

    token = await user_repo.get_or_create_subscription_token(tg_id)
    url = f"https://{settings.PUBLIC_BASE_URL}/sub/{token}"

    deleted = 0
    try:
        deleted = await key_repo.delete_all_keys_for_user(user.id, auth_token=settings.XRAY_AUTH)
    except Exception as e:
        logger.error(f"[sub_url] delete_all_keys_for_user failed user_id={user.id}: {e}")

    servers = await server_repo.get_all_servers()
    created = 0
    created_ok = 0

    for server in servers:
        try:
            _key = await key_repo.create_key(
                user_id=user.id,
                server=server,
                auth_token=settings.XRAY_AUTH,
                label=server.country,
            )
            created_ok += 1
        except Exception as e:
            logger.error(
                f"[sub_url] create_key failed user_id={user.id} server_id={server.id}: {e}"
            )
        finally:
            created += 1

    text = (
        "✅ <b>Ключи перевыпущены!</b>\n\n"
        "🔗 Ваша ссылка подписки (вставьте в приложение):\n"
        f"<code>{url}</code>\n\n"
        "ℹ️ Обновите подписку в приложении.\n\n"
        '<a href="https://telegra.ph/Lunet-VPN---instrukciya-12-18"><b>📝 Инструкция по подключению(нажмите, чтобы перейти)</b></a>'
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
    )
    await status_msg.edit_media(
        media=media,
        reply_markup=back_keys_kb(url),
        disable_web_page_preview=True,
    )