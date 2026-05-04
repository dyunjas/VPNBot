from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG
from backend.core.logger_config import logger
from backend.services import RemnaWaveService, SubscriptionService, UserService
from backend.services.exceptions import SubscriptionNotFound, UserNotFound
from bot.vpn_subscription.keyboards import back_keys_kb

router = Router()
UNEXPECTED_ERROR_TEXT = "Непредвиденная ошибка. Попробуйте позже."
SUBSCRIPTION_INACTIVE_TEXT = "Подписка неактивна."


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
    except Exception:
        return


async def _safe_send_callback_message(callback: CallbackQuery, text: str) -> None:
    try:
        if callback.message:
            await callback.message.answer(text)
        else:
            await callback.bot.send_message(chat_id=callback.from_user.id, text=text)
    except Exception:
        return


def _as_aware_utc(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _render_subscription_screen(
    callback: CallbackQuery,
    *,
    subscription,
    subscription_url: str,
):
    end_dt = _as_aware_utc(subscription.current_period_end)
    if not end_dt:
        await _safe_callback_answer(callback, "Подписка недоступна", show_alert=True)
        return

    url = subscription_url
    safe_url = escape(url, quote=False)

    auto_renew = bool(getattr(subscription, "auto_renew", False))
    auto_renew_text = escape("включено" if auto_renew else "выключено", quote=False)

    text = (
        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> <b>Ваша VPN ссылка:</b>\n"
        f"<code>{safe_url}</code>\n\n"
        f"<tg-emoji emoji-id='5956148757899776734'>📅</tg-emoji> Активна до: <b>{end_dt:%d.%m.%Y %H:%M}</b>\n"
        f"<tg-emoji emoji-id='5877410604225924969'>♻️</tg-emoji> Автопродление: <b>{auto_renew_text}</b>\n\n"
        "<tg-emoji emoji-id='5879785854284599288'>⚙️</tg-emoji> Серверы уже подготовлены. Обновите подписку в приложении.\n\n"
        "<tg-emoji emoji-id='5877318502947229960'>📖</tg-emoji>"
        "<a href='https://telegra.ph/Lunet-VPN---instrukciya-12-18'><b>Инструкция по подключению (нажмите)</b></a>"
    )

    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=back_keys_kb(url, auto_renew=auto_renew),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "vpn_subscription")
async def subscription_link(
    callback: CallbackQuery,
    user_service: UserService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnaWaveService,
):
    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id=tg_id)
    except UserNotFound:
        await _safe_send_callback_message(callback, "❌ Пользователь не найден. Перезапустите бота.")
        return

    try:
        subscription = await subscription_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        await _safe_callback_answer(callback, SUBSCRIPTION_INACTIVE_TEXT, show_alert=True)
        return

    end_dt = _as_aware_utc(subscription.current_period_end)
    now = datetime.now(timezone.utc)

    if not end_dt or end_dt <= now:
        await _safe_callback_answer(callback, SUBSCRIPTION_INACTIVE_TEXT, show_alert=True)
        return

    try:
        subscription_url = await remnawave_service.get_subscription_url(
            user=user,
            subscription=subscription,
        )
    except Exception as e:
        logger.exception(
            "[bot][subscription] remnawave error user_id=%s tg_id=%s: %s",
            user.id,
            tg_id,
            e,
        )
        await _safe_send_callback_message(callback, UNEXPECTED_ERROR_TEXT)
        return

    if not subscription_url:
        await _safe_send_callback_message(callback, UNEXPECTED_ERROR_TEXT)
        return

    await _render_subscription_screen(
        callback,
        subscription=subscription,
        subscription_url=subscription_url,
    )
    await _safe_callback_answer(callback)


@router.callback_query(F.data == "toggle_auto_renew")
async def toggle_auto_renew(
    callback: CallbackQuery,
    user_service: UserService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnaWaveService,
):
    tg_id = callback.from_user.id
    await _safe_callback_answer(callback)

    try:
        user = await user_service.get_by_tg_id(tg_id=tg_id)
    except UserNotFound:
        await _safe_callback_answer(callback, "Пользователь не найден.", show_alert=True)
        return

    try:
        current_sub = await subscription_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        await _safe_callback_answer(callback, "Подписка не найдена.", show_alert=True)
        return

    new_state = not bool(getattr(current_sub, "auto_renew", False))

    updated_sub = await subscription_service.set_auto_renew(
        user_id=user.id,
        auto_renew=new_state,
    )

    try:
        subscription_url = await remnawave_service.get_subscription_url(
            user=user,
            subscription=updated_sub,
        )
    except Exception as e:
        logger.exception(
            "[bot][subscription] toggle auto_renew error user_id=%s tg_id=%s: %s",
            user.id,
            tg_id,
            e,
        )
        await _safe_send_callback_message(callback, UNEXPECTED_ERROR_TEXT)
        return

    if not subscription_url:
        await _safe_send_callback_message(callback, UNEXPECTED_ERROR_TEXT)
        return

    await _render_subscription_screen(
        callback,
        subscription=updated_sub,
        subscription_url=subscription_url,
    )

    await _safe_callback_answer(
        callback,
        "Автопродление включено" if new_state else "Автопродление выключено"
    )
