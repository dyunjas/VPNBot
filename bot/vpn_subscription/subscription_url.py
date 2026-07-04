from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.core.logger_config import logger
from backend.images import MAIN_MENU_IMG
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


def _is_active_subscription(subscription: dict | None) -> bool:
    if not isinstance(subscription, dict):
        return False
    if str(subscription.get("status") or "").lower() != "active":
        return False
    end_value = subscription.get("current_period_end")
    if not end_value:
        return False
    try:
        end_dt = _as_aware_utc(datetime.fromisoformat(end_value))
    except Exception:
        return False
    return bool(end_dt and end_dt > datetime.now(timezone.utc))


async def _render_subscription_screen(
    callback: CallbackQuery,
    *,
    subscription,
    subscription_url: str | None,
):
    if not _is_active_subscription(subscription) or not subscription_url:
        await _safe_callback_answer(callback, SUBSCRIPTION_INACTIVE_TEXT, show_alert=True)
        return

    end_value = subscription.get("current_period_end") if isinstance(subscription, dict) else None
    end_dt = _as_aware_utc(datetime.fromisoformat(end_value)) if end_value else None
    if not end_dt:
        await _safe_callback_answer(callback, SUBSCRIPTION_INACTIVE_TEXT, show_alert=True)
        return

    safe_url = escape(subscription_url, quote=False)
    auto_renew = bool(subscription.get("auto_renew", False))
    auto_renew_text = "включено" if auto_renew else "выключено"

    text = (
        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> <b>Ваша VPN ссылка:</b>\n"
        f"<code>{safe_url}</code>\n\n"
        "<blockquote><tg-emoji emoji-id='5879785854284599288'>⚙️</tg-emoji> "
        "Трафик расходуется <b>ТОЛЬКО</b> на серверах белых списков. "
        "Гигабайты можно докупать по цене 2 RUB / гигабайт. "
        "Гигабайты переносятся между месяцами.</blockquote>\n\n"
        f"<tg-emoji emoji-id='5956148757899776734'>📅</tg-emoji> Активна до: <b>{end_dt:%d.%m.%Y %H:%M}</b>\n"
        f"<tg-emoji emoji-id='5877410604225924969'>♻️</tg-emoji> Автопродление: <b>{escape(auto_renew_text, quote=False)}</b>\n\n"
        "<tg-emoji emoji-id='5879785854284599288'>⚙️</tg-emoji> Серверы уже подготовлены. "
        "Обновите подписку в приложении.\n\n"
        "<tg-emoji emoji-id='5877318502947229960'>📖</tg-emoji>"
        "<a href='https://telegra.ph/Lunet-VPN---instrukciya-12-18'><b>Инструкция по подключению (нажмите)</b></a>"
    )

    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=back_keys_kb(subscription_url, auto_renew=auto_renew),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "vpn_subscription")
async def subscription_link(
    callback: CallbackQuery,
    bot_api,
):
    tg_id = callback.from_user.id

    try:
        await bot_api.get_user_by_tg_id(tg_id=tg_id)
    except UserNotFound:
        await _safe_send_callback_message(callback, "Пользователь не найден. Перезапустите бота.")
        return

    try:
        data = await bot_api.get_subscription_url(tg_id=tg_id)
        subscription = data.get("subscription") if isinstance(data, dict) else {}
        subscription_url = data.get("subscription_url") if isinstance(data, dict) else ""
    except SubscriptionNotFound:
        await _safe_callback_answer(callback, SUBSCRIPTION_INACTIVE_TEXT, show_alert=True)
        return
    except Exception as e:
        logger.exception(
            "[bot][subscription] subscription url error tg_id=%s: %s",
            tg_id,
            e,
        )
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
    bot_api,
):
    tg_id = callback.from_user.id
    await _safe_callback_answer(callback)

    try:
        await bot_api.get_user_by_tg_id(tg_id=tg_id)
    except UserNotFound:
        await _safe_callback_answer(callback, "Пользователь не найден.", show_alert=True)
        return

    try:
        current = await bot_api.get_subscription_url(tg_id=tg_id)
        current_sub = current.get("subscription") if isinstance(current, dict) else {}
        subscription_url = current.get("subscription_url") if isinstance(current, dict) else ""
    except SubscriptionNotFound:
        await _safe_callback_answer(callback, SUBSCRIPTION_INACTIVE_TEXT, show_alert=True)
        return

    if not _is_active_subscription(current_sub) or not subscription_url:
        await _safe_callback_answer(callback, SUBSCRIPTION_INACTIVE_TEXT, show_alert=True)
        return

    new_state = not bool(current_sub.get("auto_renew", False))

    try:
        updated = await bot_api.set_auto_renew(tg_id=tg_id, auto_renew=new_state)
        updated_sub = updated.get("subscription") if isinstance(updated, dict) else {}
        refreshed = await bot_api.get_subscription_url(tg_id=tg_id)
        subscription_url = refreshed.get("subscription_url") if isinstance(refreshed, dict) else ""
    except Exception as e:
        logger.exception(
            "[bot][subscription] toggle auto_renew error tg_id=%s: %s",
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
        "Автопродление включено" if new_state else "Автопродление выключено",
    )
