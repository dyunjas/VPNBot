import base64
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.subscription_url.utils import (
    _build_expire_only_header,
    _profile_title,
    _profile_update_interval,
    _profile_web_page,
    device_limit_response,
    expired_subscription_response,
)
from backend.core.config import settings
from backend.core.loader import bot
from backend.core.logger_config import logger
from backend.database.session import async_session
from backend.services import SubscriptionService, UserService, VPNService
from backend.services.device_service import DeviceService
from backend.services.exceptions import DeviceLimitReached, SubscriptionNotFound, UserNotFound

router = APIRouter(tags=["subscription"])

XRAY_AUTH_TOKEN = settings.XRAY_AUTH
BOT_TOKEN = settings.BOT_TOKEN


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value[:limit]


def _is_uuid_like(value: str) -> bool:
    try:
        UUID(value)
        return True
    except Exception:
        return False


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


def get_subscription_service(session: AsyncSession = Depends(get_session)) -> SubscriptionService:
    return SubscriptionService(session)


def get_vpn_service(session: AsyncSession = Depends(get_session)) -> VPNService:
    return VPNService(session=session, xray_auth_token=XRAY_AUTH_TOKEN)


def get_device_service(session: AsyncSession = Depends(get_session)) -> DeviceService:
    return DeviceService(session)


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    deny = {"authorization", "cookie", "set-cookie"}
    return {k: v for k, v in headers.items() if k.lower() not in deny}


def _extract_device_info(request: Request) -> dict[str, Any]:
    headers = {k.lower(): v for k, v in dict(request.headers).items()}
    connected_at = datetime.now(timezone.utc)
    return {
        "hwid": _clip(headers.get("x-hwid"), 128),
        "device_model": _clip(headers.get("x-device-model"), 64),
        "device_os": _clip(headers.get("x-device-os"), 32),
        "os_version": _clip(headers.get("x-ver-os"), 32),
        "device_locale": _clip(headers.get("x-device-locale"), 16),
        "user_agent": _clip(headers.get("user-agent"), 128),
        "connected_at": connected_at,
    }


async def _send_telegram_message(chat_id: int, text: str) -> None:
    if not BOT_TOKEN:
        return
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")


async def _safe_notify(chat_id: int, text: str) -> None:
    try:
        await _send_telegram_message(chat_id, text)
    except Exception:
        logger.exception("[subscription] telegram notify failed chat_id=%s", chat_id)



@router.get("/sub/{token}", response_model=None)
async def subscription(
    token: str,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    vpn_service: VPNService = Depends(get_vpn_service),
    device_service: DeviceService = Depends(get_device_service),
):
    headers: dict[str, str] = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }
    headers |= _profile_title("🌙 Lunet VPN")
    headers |= _profile_update_interval(6)
    headers |= _profile_web_page("https://t.me/LunetVpnBot")

    token = (token or "").strip()
    safe_token = token[:8] + "..." if token else ""
    if not token or not _is_uuid_like(token):
        logger.warning("[subscription] invalid token format: %s", safe_token)
        return expired_subscription_response(headers=headers)

    raw_headers = dict(request.headers)
    happ_payload: dict[str, Any] = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "method": request.method,
        "path": str(request.url.path),
        "query": dict(request.query_params),
        "headers": _sanitize_headers(raw_headers),
    }

    device = _extract_device_info(request)

    logger.info(
        "[subscription] token=%s ip=%s ua=%s hwid=%s model=%s os=%s ver=%s locale=%s",
        safe_token,
        happ_payload.get("ip"),
        happ_payload.get("user_agent"),
        device.get("hwid"),
        device.get("device_model"),
        device.get("device_os"),
        device.get("os_version"),
        device.get("device_locale"),
    )

    try:
        user = await user_service.get_by_subscription_token(token)
    except UserNotFound:
        logger.warning("[subscription] token not found: %s", safe_token)
        return expired_subscription_response(headers=headers)

    try:
        hwid = device.get("hwid")
        if hwid:
            is_new, _ = await device_service.register_device_if_new(
                user_id=user.id,
                hwid=hwid,
                device_model=device.get("device_model"),
                device_os=device.get("device_os"),
                os_version=device.get("os_version"),
                device_locale=device.get("device_locale"),
                user_agent=device.get("user_agent"),
                seen_at=device.get("connected_at"),
            )

            if is_new and user.tg_id:
                short_token = (user.subscription_token or "")[:8] if user.subscription_token else ""
                now_dt = device.get("connected_at") or datetime.now(timezone.utc)
                msg = (
                    "<tg-emoji emoji-id='5839354140261619193'>🛜</tg-emoji> "
                    "<b>Новое устройство подключено к подписке</b>\n\n"
                    f"<tg-emoji emoji-id='6005570495603282482'>🔑</tg-emoji> Подписка: <code>{short_token}</code>\n"
                    f"<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Модель: <b>{device.get('device_model') or '—'}</b>\n"
                    f"<tg-emoji emoji-id='5877318502947229960'>🧩</tg-emoji> Платформа: <b>{device.get('device_os') or '—'} / {device.get('os_version') or '—'}</b>\n"
                    f"<tg-emoji emoji-id='5778605968208170641'>🕒</tg-emoji> Время: <b>{now_dt.strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
                    "Если это не вы, перевыпустите свою VPN-ссылку в меню <b>Подписка</b>."
                )
                await _safe_notify(user.tg_id, msg)

    except DeviceLimitReached:
        logger.warning("[subscription] device limit reached user_id=%s", user.id)

        if user.tg_id:
            sub = None
            try:
                sub = await device_service.get_subscription_with_slots(user.id)
            except Exception:
                sub = None

            left = int(getattr(sub, "devices_left", 0) or 0) if sub else 0
            limit = int(getattr(sub, "devices_limit", 0) or 0) if sub else 0
            short_token = (user.subscription_token or "")[:8] if user.subscription_token else ""

            msg = (
                "<tg-emoji emoji-id='5872829476143894491'>🚫</tg-emoji> "
                "<b>Лимит устройств исчерпан</b>\n\n"
                f"<tg-emoji emoji-id='6005570495603282482'>🔑</tg-emoji> Подписка: <code>{short_token}</code>\n"
                f"<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Устройство: <b>{device.get('device_model') or '—'}</b>\n"
                f"<tg-emoji emoji-id='5877318502947229960'>🧩</tg-emoji> Платформа: <b>{device.get('device_os') or '—'} / {device.get('os_version') or '—'}</b>\n"
            )
            if limit:
                msg += f"<tg-emoji emoji-id='5967456680940671207'>🗃</tg-emoji> Лимит: <b>{left}/{limit}</b>\n\n"
            msg += "<tg-emoji emoji-id='6007942490076745785'>🧹</tg-emoji> Удалите устройство в боте и попробуйте снова."

            await _safe_notify(user.tg_id, msg)

        return device_limit_response(headers=headers)

    except Exception:
        logger.exception("[subscription] register device failed user_id=%s", user.id)

    try:
        subscription_obj = await subscription_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        return expired_subscription_response(headers=headers)

    now = datetime.now(timezone.utc)
    end_dt = subscription_obj.current_period_end
    if not end_dt:
        return expired_subscription_response(headers=headers)

    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    headers |= _build_expire_only_header(end_dt)

    if end_dt <= now:
        return expired_subscription_response(headers=headers)

    if not subscription_obj.plan:
        logger.error("[subscription] plan not loaded user_id=%s", user.id)
        return expired_subscription_response(headers=headers)

    try:
        keys_by_server = await vpn_service.get_or_create_keys(user_id=user.id)
    except Exception:
        logger.exception("[subscription] get_or_create_keys failed user_id=%s", user.id)
        return Response(content="", media_type="text/plain; charset=utf-8", headers=headers, status_code=500)

    if not keys_by_server:
        return expired_subscription_response(headers=headers)

    uris = [keys_by_server[sid] for sid in sorted(keys_by_server.keys()) if keys_by_server.get(sid)]
    if not uris:
        return expired_subscription_response(headers=headers)

    plain = "\n".join(uris).strip()
    b64 = base64.b64encode(plain.encode("utf-8")).decode("ascii")

    return Response(content=b64, media_type="text/plain; charset=utf-8", headers=headers)
