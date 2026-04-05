import asyncio
import base64
from urllib.parse import urlparse
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncGenerator
from uuid import UUID

import aiohttp

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.subscription_url.utils import (
    _build_expire_only_header,
    _profile_title,
    _profile_update_interval,
    _profile_web_page,
    device_limit_response,
    expired_subscription_response,
    traffic_limit_response,
)
from backend.core.config import settings
from backend.core.loader import bot
from backend.core.logger_config import logger
from backend.database.models import KeyStatus
from backend.database.session import async_session
from backend.services import SubscriptionService, UserService, VPNService
from backend.services.device_service import DeviceService
from backend.services.exceptions import DeviceLimitReached, SubscriptionNotFound, UserNotFound

router = APIRouter(tags=["subscription"])

XRAY_AUTH_TOKEN = settings.XRAY_AUTH
BOT_TOKEN = settings.BOT_TOKEN


def _is_browser_request(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    user_agent = (request.headers.get("user-agent") or "").lower()
    return ("text/html" in accept) or ("mozilla/" in user_agent)


def _moon_html_response() -> HTMLResponse:
    html = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Lunet</title>
  <style>
    html, body { margin: 0; height: 100%; }
    body {
      display: grid;
      place-items: center;
      background: radial-gradient(130% 90% at 0% 0%, #dbe7f8 0%, #c8d8ef 60%, #bfd0ea 100%);
    }
    img {
      width: min(280px, 74vw);
      height: auto;
      display: block;
      filter: drop-shadow(0 12px 24px rgba(35, 73, 122, 0.20));
      user-select: none;
      -webkit-user-drag: none;
    }
  </style>
</head>
<body>
  <img src="/miniapp/assets/moon.png" alt="Moon" />
</body>
</html>
"""
    return HTMLResponse(content=html)


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
    except (TypeError, ValueError, AttributeError):
        return False


def _normalize_agent_base(grpc_endpoint: str) -> str:
    grpc_endpoint = (grpc_endpoint or "").strip()
    if not grpc_endpoint:
        return ""
    parsed = urlparse(grpc_endpoint)
    if not parsed.scheme:
        return f"http://{grpc_endpoint}"
    return grpc_endpoint


def _num(value: Any) -> int:
    try:
        if value is None or isinstance(value, bool):
            return 0
        return max(0, int(float(value)))
    except (TypeError, ValueError, OverflowError):
        return 0


def _extract_traffic_ud(payload: Any) -> tuple[int, int]:
    if isinstance(payload, list):
        up, down = 0, 0
        for item in payload:
            u, d = _extract_traffic_ud(item)
            up += u
            down += d
        return up, down

    if not isinstance(payload, dict):
        return 0, 0

    up = (
        _num(payload.get("upload"))
        or _num(payload.get("uplink"))
        or _num(payload.get("up"))
        or _num(payload.get("sent"))
    )
    down = (
        _num(payload.get("download"))
        or _num(payload.get("downlink"))
        or _num(payload.get("down"))
        or _num(payload.get("recv"))
    )

    # Some agents return only total traffic.
    total = (
        _num(payload.get("total_bytes"))
        or _num(payload.get("bytes_total"))
        or _num(payload.get("traffic_bytes"))
        or _num(payload.get("total_traffic"))
        or _num(payload.get("total"))
    )
    if (not up and not down) and total:
        return 0, total

    nested_up, nested_down = 0, 0
    for key in ("data", "result", "payload", "stats", "current", "persisted", "traffic"):
        if key in payload:
            u, d = _extract_traffic_ud(payload.get(key))
            nested_up += u
            nested_down += d

    return up + nested_up, down + nested_down


async def _fetch_traffic_for_server(
    *,
    session: aiohttp.ClientSession,
    base: str,
    auth_token: str | None,
    user_id: int,
    email: str,
) -> tuple[int, int]:
    if not base:
        return 0, 0

    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    variants = (
        {"user_id": str(user_id), "email": email},
        {"email": email},
        {"user_id": str(user_id)},
    )

    for params in variants:
        try:
            async with session.get(f"{base}/user_traffic", headers=headers, params=params) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json(content_type=None)
                up, down = _extract_traffic_ud(data)
                if up or down:
                    return up, down
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            continue
    return 0, 0


async def _is_server_reachable(
    *,
    session: aiohttp.ClientSession,
    base: str,
    auth_token: str | None,
) -> bool:
    if not base:
        return False

    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        async with session.get(f"{base}/health", headers=headers) as _:
            return True
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


async def _reachable_server_ids(
    *,
    vpn_service: VPNService,
    server_ids: set[int],
) -> set[int]:
    if not server_ids:
        return set()

    servers = await vpn_service.server_repo.list_all()
    target_servers = [s for s in servers if s.id in server_ids]
    if not target_servers:
        return set()

    timeout = aiohttp.ClientTimeout(total=2)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        checks = [
            _is_server_reachable(
                session=http,
                base=_normalize_agent_base(getattr(server, "grpc_endpoint", "") or ""),
                auth_token=XRAY_AUTH_TOKEN,
            )
            for server in target_servers
        ]
        results = await asyncio.gather(*checks, return_exceptions=True)

    reachable_ids: set[int] = set()
    for server, result in zip(target_servers, results):
        if isinstance(result, Exception):
            continue
        if bool(result):
            reachable_ids.add(server.id)
    return reachable_ids


async def _sum_user_traffic_all_servers(vpn_service: VPNService, user_id: int) -> tuple[int, int]:
    servers = await vpn_service.server_repo.list_all()
    if not servers:
        return 0, 0

    email = f"user-{user_id}@lunet"
    timeout = aiohttp.ClientTimeout(total=4)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        tasks = [
            _fetch_traffic_for_server(
                session=http,
                base=_normalize_agent_base(getattr(server, "grpc_endpoint", "") or ""),
                auth_token=XRAY_AUTH_TOKEN,
                user_id=user_id,
                email=email,
            )
            for server in servers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    total_up = 0
    total_down = 0
    for item in results:
        if isinstance(item, Exception):
            continue
        up, down = item
        total_up += _num(up)
        total_down += _num(down)
    return total_up, total_down


async def _deactivate_user_keys(vpn_service: VPNService, user_id: int) -> None:
    email = f"user-{user_id}@lunet"
    keys = await vpn_service.key_repo.list_user_keys_by_status(
        user_id=user_id,
        statuses=[KeyStatus.active],
        with_server=True,
    )
    if not keys:
        return

    headers = {"Content-Type": "application/json"}
    if XRAY_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {XRAY_AUTH_TOKEN}"

    processed_server_ids: set[int] = set()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as http:
        for key in keys:
            if key.server_id and key.server_id in processed_server_ids:
                continue
            if key.server_id:
                processed_server_ids.add(key.server_id)

            server = getattr(key, "server", None)
            base = _normalize_agent_base(getattr(server, "grpc_endpoint", "") if server else "")
            if base:
                try:
                    await http.post(
                        f"{base}/remove_user",
                        headers=headers,
                        json={"email": email},
                    )
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    logger.warning(
                        "[subscription] remove_user failed during traffic lock user_id=%s server_id=%s",
                        user_id,
                        key.server_id,
                    )

            try:
                await vpn_service.key_repo.set_status(key.id, KeyStatus.deleted)
            except Exception:
                logger.warning(
                    "[subscription] set_status deleted failed user_id=%s key_id=%s",
                    user_id,
                    key.id,
                )

    await vpn_service.session.commit()


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
    if _is_browser_request(request):
        return _moon_html_response()

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
        if not hwid:
            logger.warning(
                "[subscription] hwid missing user_id=%s token=%s ua=%s",
                user.id,
                safe_token,
                happ_payload.get("user_agent"),
            )
            return Response(
                content="Приложение не поддерживается, обратитесь в поддержку.",
                media_type="text/plain; charset=utf-8",
                headers=headers,
                status_code=400,
            )

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

    if not subscription_obj.plan:
        logger.error("[subscription] plan not loaded user_id=%s", user.id)
        return expired_subscription_response(headers=headers)

    # Aggregate user traffic from all configured servers via /user_traffic.
    used_upload = 0
    used_download = 0
    try:
        used_upload, used_download = await _sum_user_traffic_all_servers(vpn_service=vpn_service, user_id=user.id)
    except Exception:
        logger.exception("[subscription] aggregate traffic failed user_id=%s", user.id)
        used_upload, used_download = 0, 0

    gb_limit = 0
    try:
        gb_limit = int(getattr(subscription_obj.plan, "gb_limit", 0) or 0)
    except Exception:
        gb_limit = 0

    topup_gb = Decimal(0)
    try:
        topup_gb = await subscription_service.get_topup_gb(subscription_id=subscription_obj.id)
    except Exception:
        logger.exception("[subscription] failed to load topup_gb user_id=%s", user.id)
        topup_gb = Decimal(0)

    total_gb_limit = Decimal(gb_limit) + Decimal(topup_gb or 0)
    if total_gb_limit < 0:
        total_gb_limit = Decimal(0)
    total_limit_bytes = int(total_gb_limit * Decimal(1024**3))

    headers |= _build_expire_only_header(end_dt)
    expire_unix = int(end_dt.timestamp())
    used_total = max(0, int(used_upload) + int(used_download))

    # Persist remaining traffic into vpn_subscriptions.gb_left:
    # gb_left = (plan_gb_limit + topup_gb) - used_gb
    try:
        used_gb = (Decimal(used_total) / Decimal(1024**3)) if used_total > 0 else Decimal(0)
        gb_left = total_gb_limit - used_gb
        if gb_left < 0:
            gb_left = Decimal(0)
        subscription_obj.gb_left = gb_left.quantize(Decimal("0.01"))
        await subscription_service.session.commit()
    except Exception:
        logger.exception("[subscription] failed to persist gb_left user_id=%s", user.id)

    headers["Subscription-Userinfo"] = (
        f"upload={max(0, int(used_upload))}; "
        f"download={max(0, int(used_download))}; "
        f"total={int(total_limit_bytes)}; "
        f"expire={expire_unix}"
    )

    # Traffic limit reached: deactivate keys and return explicit guidance.
    if total_limit_bytes > 0 and used_total >= total_limit_bytes:
        try:
            await _deactivate_user_keys(vpn_service=vpn_service, user_id=user.id)
        except Exception:
            logger.exception("[subscription] failed to deactivate keys on traffic limit user_id=%s", user.id)
        return traffic_limit_response(headers=headers)

    if end_dt <= now:
        return expired_subscription_response(headers=headers)

    try:
        keys_by_server = await vpn_service.get_or_create_keys(user_id=user.id)
    except Exception:
        logger.exception("[subscription] get_or_create_keys failed user_id=%s", user.id)
        return Response(content="", media_type="text/plain; charset=utf-8", headers=headers, status_code=500)

    if not keys_by_server:
        return expired_subscription_response(headers=headers)

    ordered_servers = await vpn_service.server_repo.list_all()
    reachable_ids = await _reachable_server_ids(
        vpn_service=vpn_service,
        server_ids=set(keys_by_server.keys()),
    )

    filtered_keys_by_server = {sid: uri for sid, uri in keys_by_server.items() if sid in reachable_ids}

    ordered_server_ids = [s.id for s in ordered_servers if s.id in filtered_keys_by_server]
    ordered_server_ids_set = set(ordered_server_ids)
    remaining_ids = sorted([sid for sid in filtered_keys_by_server.keys() if sid not in ordered_server_ids_set])
    uris = [
        filtered_keys_by_server[sid]
        for sid in ordered_server_ids + remaining_ids
        if filtered_keys_by_server.get(sid)
    ]
    if not uris:
        return expired_subscription_response(headers=headers)

    plain = "\n".join(uris).strip()
    b64 = base64.b64encode(plain.encode("utf-8")).decode("ascii")

    return Response(content=b64, media_type="text/plain; charset=utf-8", headers=headers)


