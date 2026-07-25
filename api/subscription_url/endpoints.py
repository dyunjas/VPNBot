from __future__ import annotations

import os
from datetime import datetime, timezone
from html import escape
from typing import Any, AsyncGenerator

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.core.config import settings
from backend.core.telegram import create_telegram_session
from backend.database.models import User, Subscription, SubStatus
from backend.database.session import async_session
from backend.images import MAIN_MENU_IMG
from backend.services.activity_service import ActivityService
from backend.services import BillingService, UserService
from backend.core.loader import bot as runtime_bot
from backend.services.exceptions import InsufficientBalance, PurchaseInProgress, TooEarlyToRenew

router = APIRouter(tags=["subscription"])


def _webhook_secret() -> str:
    return (os.getenv("REMNAWAVE_WEBHOOK_SECRET") or "").strip()


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value[:limit]


def _parse_iso_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        txt = str(value).strip()
        if not txt:
            return None
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        dt = datetime.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


class RemnawaveWebhookPayload(BaseModel):
    scope: str | None = None
    event: str | None = None
    timestamp: str | None = None
    data: dict[str, Any] | None = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


async def _send_telegram_message(chat_id: int, text: str, *, photo=None, reply_markup=None) -> None:

    bot_instance = runtime_bot
    temp_bot: Bot | None = None
    if bot_instance is None:
        bot_token = (settings.BOT_TOKEN or "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is not configured")
        temp_bot = Bot(token=bot_token, session=create_telegram_session())
        bot_instance = temp_bot
    try:
        if photo is not None:
            await bot_instance.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return

        await bot_instance.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()


async def _safe_notify(chat_id: int, text: str, *, photo=None, reply_markup=None) -> None:
    try:
        await _send_telegram_message(chat_id, text, photo=photo, reply_markup=reply_markup)
    except Exception:
        logger.exception("[webhook][remnawave] telegram notify failed chat_id=%s", chat_id)


async def _find_user_for_webhook(session: AsyncSession, payload: RemnawaveWebhookPayload) -> User | None:
    data = payload.data or {}
    remote_user = data.get("user") if isinstance(data.get("user"), dict) else {}
    if not remote_user and isinstance(data, dict):
        remote_user = data

    remote_uuid = str(remote_user.get("uuid") or "").strip()
    if remote_uuid:
        res = await session.execute(select(User).where(User.remnawave_user_uuid == remote_uuid))
        user = res.scalar_one_or_none()
        if user:
            return user

    remote_id = remote_user.get("id")
    if remote_id is not None:
        try:
            remote_id_int = int(remote_id)
        except (TypeError, ValueError):
            remote_id_int = None
        if remote_id_int is not None:
            res = await session.execute(select(User).where(User.remnawave_user_id == remote_id_int))
            user = res.scalar_one_or_none()
            if user:
                return user

    tg_id = remote_user.get("telegramId")
    if tg_id is not None:
        try:
            tg_id_int = int(tg_id)
        except (TypeError, ValueError):
            tg_id_int = None
        if tg_id_int is not None:
            res = await session.execute(select(User).where(User.tg_id == tg_id_int))
            user = res.scalar_one_or_none()
            if user:
                return user

    return None


def _extract_expiration_hours(payload: RemnawaveWebhookPayload) -> int | None:
    data = payload.data or {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    raw_meta_expiration = meta.get("expiration")
    if raw_meta_expiration is not None:
        try:
            value = int(raw_meta_expiration)
            if value > 0:
                return value
        except Exception:
            pass

    expire_at = _parse_iso_dt(data.get("expireAt"))
    event_at = _parse_iso_dt(payload.timestamp) or datetime.now(timezone.utc)
    if not expire_at:
        return None
    remain_hours = round((expire_at - event_at).total_seconds() / 3600)
    return remain_hours if remain_hours > 0 else None


async def _find_latest_subscription(session: AsyncSession, *, user_id: int) -> Subscription | None:
    res = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.current_period_end.desc(), Subscription.id.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _notify_expiration_warning(*, tg_id: int, hours: int) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Продлить подписку", callback_data="subscription")
    builder.adjust(1)

    if hours >= 48:
        remaining_text = "2 дня"
    elif hours >= 24:
        remaining_text = "1 день"
    else:
        remaining_text = f"примерно {hours} ч."

    text = (
        "<b><tg-emoji emoji-id='5967412305338568701'>📅</tg-emoji> Ваша подписка скоро закончится</b>\n\n"
        f"До окончания осталось <b>{remaining_text}</b>.\n\n"
        "<blockquote> Продлите подписку заранее, чтобы VPN продолжил работать без перерыва. </blockquote>\n\n"
        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> После продления ссылка для подключения останется прежней.\n\n"
        "<i><tg-emoji emoji-id='6005843436479975944'>🔁</tg-emoji> Если автопродление включено, убедитесь, что на балансе достаточно средств.</i>"
    )
    await _safe_notify(
        tg_id,
        text,
        photo=MAIN_MENU_IMG,
        reply_markup=builder.as_markup()
    )

async def _notify_subscription_expired(*, tg_id: int) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="Продлить подписку", callback_data="subscription", icon_custom_emoji_id="5967456680940671207", style="primary")
    builder.adjust(1)

    text = (
        "<b><tg-emoji emoji-id='5967412305338568701'>📅</tg-emoji> Ваша подписка закончилась</b>\n\n"
        "Доступ к VPN временно приостановлен.\n\n"
        "<blockquote> Продлите подписку, и сервис снова заработает по вашей текущей ссылке. </blockquote>\n\n"
        "<i><tg-emoji emoji-id='6005843436479975944'>🔁</tg-emoji> Если вы уже продлили подписку, обновите её в VPN-приложении.</i>"
    )
    await _safe_notify(
        tg_id,
        text,
        photo=MAIN_MENU_IMG,
        reply_markup=builder.as_markup()
    )


async def _notify_subscription_renewed(*, tg_id: int, end_dt: datetime) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Моя подписка", callback_data="vpn_subscription")
    builder.adjust(1)

    text = (
        "<b><tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Подписка продлена автоматически</b>\n\n"
        f"<blockquote> <tg-emoji emoji-id='5967412305338568701'>📅</tg-emoji> Новая дата окончания: <b>{end_dt:%d.%m.%Y %H:%M}</b>\n"
        "<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Средства списаны с вашего баланса </blockquote>\n\n"
        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> Ссылка для подключения осталась прежней."
    )
    await _safe_notify(
        tg_id,
        text,
        photo=MAIN_MENU_IMG,
        reply_markup=builder.as_markup()
    )


def _extract_hwid_device(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("hwidUserDevice", "userHwidDevice", "hwid_user_device", "device"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _device_emoji(platform: str, user_agent: str) -> str:
    raw = f"{platform} {user_agent}".lower()
    if "android" in raw:
        return "<tg-emoji emoji-id='5819078828017849357'>📱</tg-emoji>"
    if any(value in raw for value in ("apple", "ios", "iphone", "ipad", "macos", "mac os", "darwin")):
        return "<tg-emoji emoji-id='5818920837645867167'>📱</tg-emoji>"
    if "windows" in raw:
        return "<tg-emoji emoji-id='5818956713507689486'>💻</tg-emoji>"
    return "<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji>"


def _app_version(user_agent: str) -> str:
    value = (user_agent or "").strip()
    if not value:
        return "—"

    first_part = value.split(maxsplit=1)[0]
    parts = [part for part in first_part.split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return "—"


def _device_title(device_model: str | None, device_os: str | None, hwid: str | None) -> str:
    return device_model or device_os or hwid or "Устройство"


@router.post("/remnawave-webhook")
async def remnawave_webhook(
    request: Request,
    payload: RemnawaveWebhookPayload,
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
    user_service: UserService = Depends(get_user_service),
):
    expected_secret = _webhook_secret()
    if expected_secret:
        provided_secret = (x_webhook_token or request.query_params.get("token") or "").strip()
        if provided_secret != expected_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

    scope = str(payload.scope or "").strip()
    event = str(payload.event or "").strip()
    if scope == "user":
        async with async_session() as session:
            user = await _find_user_for_webhook(session, payload)
            if not user:
                logger.warning(
                    "[webhook][remnawave] user event ignored: user not found event=%s payload_user=%s",
                    event,
                    (payload.data or {}),
                )
                return {"ok": False, "error": "user_not_found", "event": event}

            activity_service = ActivityService(session)

            expiration_event_hours = {
                "expires_in_48_hours": 48,
                "user.expires_in_48_hours": 48,
                "expires_in_24_hours": 24,
                "user.expires_in_24_hours": 24,
            }
            if event in expiration_event_hours or event == "user.expiration":
                hours = expiration_event_hours.get(event)
                if hours is None:
                    hours = _extract_expiration_hours(payload)
                if hours not in (24, 48):
                    logger.info(
                        "[webhook][remnawave] expiration ignored user_id=%s hours=%s",
                        user.id,
                        hours,
                    )
                    return {"ok": True, "ignored": True, "event": event, "hours": hours}

                if user.tg_id:
                    await _notify_expiration_warning(tg_id=int(user.tg_id), hours=hours)
                await activity_service.log_user_event(
                    user_id=user.id,
                    category="webhook",
                    action="subscription_expiration_warning",
                    source="remnawave",
                    note=f"Получен webhook {event} за {hours} ч.",
                )
                await session.commit()
                logger.info(
                    "[webhook][remnawave] expiration processed user_id=%s event=%s hours=%s",
                    user.id,
                    event,
                    hours,
                )
                return {"ok": True, "event": event, "hours": hours}

            if event == "user.expired":
                user_id = int(user.id)
                user_tg_id = int(user.tg_id) if user.tg_id else None
                subscription = await _find_latest_subscription(session, user_id=user.id)
                if subscription and bool(subscription.auto_renew):
                    subscription_id = int(subscription.id)
                    plan_id = int(subscription.plan_id)
                    billing_service = BillingService(session)
                    try:
                        renewed = await billing_service.buy_subscription(
                            user_id=user_id,
                            plan_id=plan_id,
                            auto_renew=True,
                        )
                        end = renewed.current_period_end
                        if end and end.tzinfo is None:
                            end = end.replace(tzinfo=timezone.utc)
                        elif end:
                            end = end.astimezone(timezone.utc)

                        if user_tg_id and end:
                            await _notify_subscription_renewed(tg_id=user_tg_id, end_dt=end)

                        await ActivityService(session).log_user_event(
                            user_id=user_id,
                            category="webhook",
                            action="subscription_auto_renewed",
                            source="remnawave",
                            subscription_id=renewed.id,
                            note="Получен webhook user.expired, подписка автоматически продлена",
                        )
                        await session.commit()
                        logger.info(
                            "[webhook][remnawave] expired auto-renewed user_id=%s subscription_id=%s",
                            user_id,
                            renewed.id,
                        )
                        return {
                            "ok": True,
                            "event": event,
                            "auto_renewed": True,
                            "subscription_id": renewed.id,
                        }
                    except PurchaseInProgress:
                        await session.rollback()
                        logger.info(
                            "[webhook][remnawave] expired auto-renew skipped: purchase in progress user_id=%s subscription_id=%s",
                            user_id,
                            subscription_id,
                        )
                        return {
                            "ok": True,
                            "event": event,
                            "auto_renew_pending": True,
                            "subscription_id": subscription_id,
                        }
                    except TooEarlyToRenew:
                        await session.rollback()
                        logger.info(
                            "[webhook][remnawave] expired auto-renew skipped: too early user_id=%s subscription_id=%s",
                            user_id,
                            subscription_id,
                        )
                        return {
                            "ok": True,
                            "event": event,
                            "auto_renew_skipped": "too_early",
                            "subscription_id": subscription_id,
                        }
                    except InsufficientBalance:
                        await session.rollback()
                        logger.info(
                            "[webhook][remnawave] expired auto-renew failed user_id=%s subscription_id=%s reason=%s",
                            user_id,
                            subscription_id,
                            "InsufficientBalance",
                        )
                        user = await session.get(User, user_id)
                        subscription = await _find_latest_subscription(session, user_id=user_id)
                        activity_service = ActivityService(session)
                    except Exception as e:
                        await session.rollback()
                        logger.exception(
                            "[webhook][remnawave] expired auto-renew error user_id=%s subscription_id=%s: %s",
                            user_id,
                            subscription_id,
                            e,
                        )
                        user = await session.get(User, user_id)
                        subscription = await _find_latest_subscription(session, user_id=user_id)
                        activity_service = ActivityService(session)
                    finally:
                        await billing_service.close_clients()

                if subscription:
                    expire_at = _parse_iso_dt((payload.data or {}).get("expireAt")) or datetime.now(timezone.utc)
                    subscription.status = SubStatus.expired
                    subscription.current_period_end = expire_at
                    subscription.next_renewal_at = expire_at
                if user:
                    user.traffic_limit_bytes = 0
                if user_tg_id:
                    await _notify_subscription_expired(tg_id=user_tg_id)
                await activity_service.log_user_event(
                    user_id=user_id,
                    category="webhook",
                    action="subscription_expired",
                    source="remnawave",
                    subscription_id=getattr(subscription, "id", None),
                    note="Получен webhook user.expired, локальная подписка переведена в expired",
                )
                await session.commit()
                logger.info(
                    "[webhook][remnawave] expired processed user_id=%s subscription_id=%s",
                    user_id,
                    getattr(subscription, "id", None),
                )
                return {"ok": True, "event": event, "subscription_id": getattr(subscription, "id", None)}

        logger.info("[webhook][remnawave] ignored user event=%s", event)
        return {"ok": True, "ignored": True, "event": event}

    if scope and scope != "user_hwid_devices":
        logger.info("[webhook][remnawave] ignored scope=%s event=%s", scope, event)
        return {"ok": True, "ignored": True, "scope": scope, "event": event}
    if event != "user_hwid_devices.added":
        logger.info("[webhook][remnawave] ignored event=%s", event)
        return {"ok": True, "ignored": True, "event": event}

    data = payload.data or {}
    hwid_device = _extract_hwid_device(data)
    hwid = _clip(hwid_device.get("hwid"), 128)
    if not hwid:
        logger.warning("[webhook][remnawave] hwid missing payload=%s", payload.model_dump())
        return {"ok": False, "error": "hwid_missing"}

    user: User | None = await _find_user_for_webhook(user_service.session, payload)
    if not user:
        logger.warning(
            "[webhook][remnawave] user not found scope=%s event=%s payload_user=%s",
            scope,
            event,
            (data.get("user") or {}),
        )
        return {"ok": False, "error": "user_not_found"}

    device_model = _clip(hwid_device.get("deviceModel"), 64)
    device_os = _clip(hwid_device.get("platform"), 32)
    os_version = _clip(hwid_device.get("osVersion"), 32)
    user_agent = _clip(hwid_device.get("userAgent"), 512)

    if user.tg_id:
        device_emoji = _device_emoji(device_os or "", user_agent or "")
        app_version = _app_version(user_agent or "")
        title = _device_title(device_model, device_os, hwid)
        msg = (
            "<b><tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> Новое устройство подключено!</b>\n\n"
            f"{device_emoji} <b>{escape(str(title))}</b>\n\n"
            "<blockquote>"
            f"<tg-emoji emoji-id='5877318502947229960'>💻</tg-emoji> Модель: <b>{escape(str(device_model or '—'))}</b>\n"
            f"<tg-emoji emoji-id='5985774024968379294'>🖊</tg-emoji> Платформа: <b>{escape(str(device_os or '—'))}</b>\n"
            f"<tg-emoji emoji-id='5935938364086685805'>➕</tg-emoji> Версия ОС: <b>{escape(str(os_version or '—'))}</b>\n"
            f"<tg-emoji emoji-id='5967456680940671207'>🗃</tg-emoji> Версия приложения: <b>{escape(app_version)}</b>\n"
            "</blockquote>\n\n"
            f"<b>User-Agent:</b> <code>{escape(str(user_agent or '—'))}</code>\n\n"
            f"<b>HWID:</b> <code>{escape(str(hwid or '—'))}</code>\n\n"
            "Если вы не подключали это устройство, откройте <b>Моя подписка -> Устройства</b> и удалите его, после обратитесь в поддержку."
        )
        builder = InlineKeyboardBuilder()
        builder.button(
            text="Устройства",
            callback_data="subscription_devices",
            icon_custom_emoji_id="5877318502947229960",
            style="primary",
        )
        builder.adjust(1)
        await _safe_notify(user.tg_id, msg, reply_markup=builder.as_markup())

    logger.info(
        "[webhook][remnawave] processed scope=%s event=%s user_id=%s hwid=%s",
        scope,
        event,
        user.id,
        hwid,
    )
    return {"ok": True, "scope": scope, "event": event}
