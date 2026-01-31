from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from bot.vpn_subscription.reissue_keys.keyboards import reissue_keys_kb
from bot.vpn_subscription.keyboards import back_keys_kb

from backend.images import MAIN_MENU_IMG
from backend.repositories.user_repository import UserRepository
from backend.repositories.subscription_repository import SubscriptionRepository
from backend.repositories.server_repository import ServerRepository
from backend.repositories.key_repository import KeyRepository

from backend.services import UserService, SubscriptionService, VPNService
from backend.services.exceptions import UserNotFound

from backend.core.config import settings
from backend.core.logger_config import logger

from datetime import datetime

router = Router()

@router.callback_query(F.data == "reissue_keys")
async def reissue_keys_clb(callback: CallbackQuery):
    text = (
        "<tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Вы уверены, что хотите перевыпустить ключи?\n\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> После перевыпуска вам нужно будет обновить подписку в приложении.</i>"
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
async def confirm_reissue_keys(
    callback: CallbackQuery,
    user_service: UserService,
    subscription_service: SubscriptionService,
    vpn_service: VPNService,
):
    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id=tg_id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    subscription = await subscription_service.get_active_subscription(user_id=user.id)
    if not subscription or subscription.current_period_end <= datetime.now():
        await callback.answer(
            text=(
                "У вас нет активной подписки.\n"
                "Оформите подписку, чтобы получить ссылку."
            ),
            show_alert=True,
        )
        return

    status_text = (
        "<tg-emoji emoji-id='5843799474362652262'>🔄</tg-emoji> <b>Перевыпускаю ключи...</b>\n\n"
        "Пожалуйста, подождите до 60 секунд."
    )
    await callback.message.edit_media(
        InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=status_text,
            parse_mode="HTML",
        )
    )
    await callback.answer()

    try:
        await vpn_service.reissue_keys(user_id=user.id)
    except Exception as e:
        logger.exception(
            f"[confirm_reissue_keys] reissue failed user_id={user.id}: {e}"
        )
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Не удалось перевыпустить ключи. Попробуйте позже."
        )
        return


    token = await user_service.get_subscription_token(user_id=user.id)
    url = f"https://{settings.PUBLIC_BASE_URL}/sub/{token}"

    final_text = (
        "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> <b>Ключи перевыпущены!</b>\n\n"
        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> <b>Ваша VPN ссылка:</b>\n"
        f"<code>{url}</code>\n\n"
        f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Активна до: <b>{subscription.current_period_end:%d.%m.%Y %H:%M}</b>\n\n"
        "<tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Серверы уже подготовлены. Вы можете обновить подписку в приложение.\n\n"
        "<tg-emoji emoji-id='5877318502947229960'>💻</tg-emoji>"
        f'<a href="https://telegra.ph/Lunet-VPN---instrukciya-12-18"><b>Инструкция по подключению(нажмите, чтобы перейти)</b></a>'
    )

    await callback.message.edit_media(
        InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=final_text,
            parse_mode="HTML",
        ),
        reply_markup=back_keys_kb(url),
        disable_web_page_preview=True,
    )
