from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from aiogram import Bot
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.core.telegram import create_telegram_session
from backend.database.models import User, Subscription, SubStatus
from backend.database.session import async_session
from backend.services import UserService

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


async def _send_telegram_message(chat_id: int, text: str) -> None:
    from entry_api import runtime_bot

    bot_instance = runtime_bot
    temp_bot: Bot | None = None
    if bot_instance is None:
        bot_token = (os.getenv("BOT_TOKEN") or "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is not configured")
        temp_bot = Bot(token=bot_token, session=create_telegram_session())
        bot_instance = temp_bot
    try:
        await bot_instance.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()


async def _safe_notify(chat_id: int, text: str) -> None:
    try:
        await _send_telegram_message(chat_id, text)
    except Exception:
        logger.exception("[webhook][remnawave] telegram notify failed chat_id=%s", chat_id)


async def _find_user_for_webhook(session: AsyncSession, payload: RemnawaveWebhookPayload) -> User | None:
    data = payload.data or {}
    remote_user = data.get("user") if isinstance(data.get("user"), dict) else {}

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


def _extract_hwid_device(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("hwidUserDevice", "userHwidDevice", "hwid_user_device", "device"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _extract_token_from_url(url: str | None) -> str | None:
    if not isinstance(url, str):
        return None
    value = url.strip().rstrip("/")
    if not value:
        return None
    parts = value.split("/")
    return parts[-1] if parts else None


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

    connected_at = _parse_iso_dt(hwid_device.get("createdAt")) or _parse_iso_dt(payload.timestamp) or datetime.now(timezone.utc)
    device_model = _clip(hwid_device.get("deviceModel"), 64)
    device_os = _clip(hwid_device.get("platform"), 32)
    os_version = _clip(hwid_device.get("osVersion"), 32)

    if user.tg_id:
        res_sub = await user_service.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.status == SubStatus.active)
            .order_by(Subscription.current_period_end.desc())
            .limit(1)
        )
        active_sub = res_sub.scalar_one_or_none()
        token = (getattr(active_sub, "subscription_token", None) or _extract_token_from_url(user.subscription_url) or "")
        short_token = token[:8] if token else ""
        now_dt = connected_at or datetime.now(timezone.utc)
        msg = (
            "<tg-emoji emoji-id='5839354140261619193'>🛜</tg-emoji> "
            "<b>Новое устройство подключено к подписке</b>\n\n"
            f"<tg-emoji emoji-id='6005570495603282482'>🔑</tg-emoji> Подписка: <code>{short_token}</code>\n"
            f"<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Модель: <b>{device_model or '—'}</b>\n"
            f"<tg-emoji emoji-id='5877318502947229960'>🧩</tg-emoji> Платформа: <b>{device_os or '—'} / {os_version or '—'}</b>\n"
            f"<tg-emoji emoji-id='5778605968208170641'>🕒</tg-emoji> Время: <b>{now_dt.strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
            "Если это не вы, удалите устройство в меню <b>Подписка</b>."
        )
        await _safe_notify(user.tg_id, msg)

    logger.info(
        "[webhook][remnawave] processed scope=%s event=%s user_id=%s hwid=%s",
        scope,
        event,
        user.id,
        hwid,
    )
    return {"ok": True, "scope": scope, "event": event}
