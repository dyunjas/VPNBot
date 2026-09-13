from __future__ import annotations

import os
import secrets
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Literal

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from api.miniapp.common import _get_tg_user
from backend.core.config import settings
from backend.core.loader import bot
from backend.core.logger_config import logger
from backend.database.models import User
from backend.database.session import async_session
from backend.email_templates import render_code_email
from backend.services import (
    BillingService,
    PromoService,
    ReferralService,
    RemnaWaveService,
    SubscriptionService,
    TransactionService,
    UserService,
    WithdrawalService,
)
from backend.services.exceptions import (
    BannedUser,
    InsufficientBalance,
    NotEnoughReferralBalance,
    PaymentNotConfirmed,
    PlanNotFound,
    PromocodeAlreadyUsed,
    PromocodeExhausted,
    PromocodeNotFound,
    PurchaseInProgress,
    SubscriptionNotFound,
    TooEarlyToRenew,
    TransactionNotFound,
    UserNotFound,
)

JWT_ALG = "HS256"
OTP_TTL_SEC = 600
ACCESS_TTL_MIN = 30
REFRESH_TTL_DAYS = 30
REFRESH_COOKIE = "cabinet_refresh_token"

_OTP_STORE: dict[str, dict] = {}
_OTP_LAST_SENT: dict[str, float] = {}
_OTP_SEND_HISTORY: dict[str, list[float]] = {}
_OTP_SEND_COOLDOWN_SEC = 30
_OTP_TG_LOGIN_WINDOW_SEC = 600
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1


class SendEmailCodePayload(BaseModel):
    email: str
    tg_id: int | None = None


class SendTelegramCodePayload(BaseModel):
    tg_id: int


class VerifyCodePayload(BaseModel):
    channel: Literal["email", "telegram"]
    email: str | None = None
    tg_id: int | None = None
    code: str = Field(min_length=4, max_length=8)


class RegisterPayload(BaseModel):
    email: str
    initData: str | None = None


class InitPayload(BaseModel):
    initData: str | None = None


class DeleteDevicePayload(InitPayload):
    device_id: int


class BuySubscriptionPayload(InitPayload):
    plan_id: int


class BuyTrafficPayload(InitPayload):
    gb: int


class BuyDeviceSlotsPayload(InitPayload):
    slots: int = Field(ge=1, le=20)


class GiftSubscriptionPayload(InitPayload):
    plan_id: int
    recipient: str = Field(min_length=1, max_length=64)


class TopupPayload(InitPayload):
    amount: int
    method: str = "platega"
    asset: str = "USDT"
    platega_type: str = "card"


class BalanceCheckPayload(InitPayload):
    method: str = "platega"
    provider_id: str | None = None


class ApplyPromocodePayload(InitPayload):
    code: str


class CreateWithdrawalPayload(InitPayload):
    amount: int
    method: str


class ReferralTransferPayload(InitPayload):
    amount: int


def _jwt_secret() -> str:
    secret = (settings.SECRET_KEY or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="SECRET_KEY is not configured")
    return secret


def _create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "scope": "cabinet:web",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)


def _create_refresh_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "scope": "cabinet:refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALG])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


async def require_cabinet_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> int:
    raw = (authorization or "").strip()
    if not raw.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = raw[7:].strip()
    payload = _decode_token(token)
    if payload.get("scope") != "cabinet:web":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


async def require_optional_cabinet_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> int | None:
    raw = (authorization or "").strip()
    if not raw:
        return None
    if not raw.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = raw[7:].strip()
    payload = _decode_token(token)
    if payload.get("scope") != "cabinet:web":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


def _resolve_request_user_id(init_data: str | None, user_id: int | None) -> int:
    if user_id is not None:
        return user_id
    tg_user = _get_tg_user(init_data)
    return int(tg_user["id"])


def _otp_key(channel: str, identity: str) -> str:
    return f"{channel}:{identity.strip().lower()}"


def _cleanup_otp() -> None:
    now = int(time.time())
    stale = [key for key, value in _OTP_STORE.items() if int(value.get("expires_at", 0)) < now]
    for key in stale:
        _OTP_STORE.pop(key, None)


def _put_otp(channel: str, identity: str, user_id: int, code: str) -> None:
    _cleanup_otp()
    key = _otp_key(channel, identity)
    now_ts = time.time()
    _OTP_STORE[key] = {
        "user_id": user_id,
        "code": code,
        "expires_at": int(time.time()) + OTP_TTL_SEC,
    }
    _OTP_LAST_SENT[key] = now_ts
    history = [ts for ts in _OTP_SEND_HISTORY.get(key, []) if (now_ts - ts) < _OTP_TG_LOGIN_WINDOW_SEC]
    history.append(now_ts)
    _OTP_SEND_HISTORY[key] = history


def _otp_send_allowed(
    channel: str,
    identity: str,
    *,
    cooldown_sec: int | None = None,
    window_sec: int | None = None,
    max_sends: int | None = None,
) -> bool:
    key = _otp_key(channel, identity)
    cooldown = int(cooldown_sec or _OTP_SEND_COOLDOWN_SEC)
    last_sent = float(_OTP_LAST_SENT.get(key, 0) or 0)
    now_ts = time.time()
    if (now_ts - last_sent) < cooldown:
        return False
    if window_sec and max_sends:
        history = [ts for ts in _OTP_SEND_HISTORY.get(key, []) if (now_ts - ts) < int(window_sec)]
        _OTP_SEND_HISTORY[key] = history
        if len(history) >= int(max_sends):
            return False
    return True


def _otp_send_retry_after(
    channel: str,
    identity: str,
    *,
    cooldown_sec: int | None = None,
    window_sec: int | None = None,
    max_sends: int | None = None,
) -> int:
    key = _otp_key(channel, identity)
    cooldown = int(cooldown_sec or _OTP_SEND_COOLDOWN_SEC)
    now_ts = time.time()
    retry_after = 0

    last_sent = float(_OTP_LAST_SENT.get(key, 0) or 0)
    if last_sent:
        retry_after = max(retry_after, int(max(0, cooldown - (now_ts - last_sent)) + 0.999))

    if window_sec and max_sends:
        history = [ts for ts in _OTP_SEND_HISTORY.get(key, []) if (now_ts - ts) < int(window_sec)]
        _OTP_SEND_HISTORY[key] = history
        if len(history) >= int(max_sends):
            oldest_relevant = history[-int(max_sends)]
            retry_after = max(
                retry_after,
                int(max(0, int(window_sec) - (now_ts - oldest_relevant)) + 0.999),
            )
    return retry_after


def _pop_otp(channel: str, identity: str, code: str) -> int | None:
    _cleanup_otp()
    key = _otp_key(channel, identity)
    rec = _OTP_STORE.get(key)
    if not rec or str(rec.get("code")) != str(code).strip():
        return None
    _OTP_STORE.pop(key, None)
    return int(rec.get("user_id"))


def _smtp_send_code(email: str, code: str, purpose: str = "login") -> None:
    host = (os.getenv("SMTP_HOST") or getattr(settings, "SMTP_HOST", None) or "").strip()
    user = (os.getenv("SMTP_USER") or getattr(settings, "SMTP_USER", None) or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or getattr(settings, "SMTP_PASSWORD", None) or "").strip()
    from_email = (os.getenv("SMTP_FROM_EMAIL") or getattr(settings, "SMTP_FROM_EMAIL", None) or user or "").strip()
    raw_port = os.getenv("SMTP_PORT") or str(getattr(settings, "SMTP_PORT", 587) or 587)
    port = int(str(raw_port).strip() or 587)
    if not host or not from_email:
        logger.error("[cabinet][smtp] not configured host=%r from_email=%r user=%r port=%r", host, from_email, user, raw_port)
        raise HTTPException(status_code=503, detail="SMTP is not configured")

    html_body, plain_body = render_code_email(code, purpose=purpose)
    msg = EmailMessage()
    msg["Subject"] = "Подтверждение email Lunet" if purpose == "bind" else ("Код подтверждения Lunet" if purpose == "admin_login" else "Код входа Lunet")
    msg["From"] = f"Lunet <{from_email}>"
    msg["To"] = email
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            if user:
                server.login(user, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        if user:
            server.login(user, password)
        server.send_message(msg)


def _map_service_error(e: Exception) -> HTTPException:
    if isinstance(e, UserNotFound):
        return HTTPException(status_code=404, detail="Пользователь не найден")
    if isinstance(e, PlanNotFound):
        return HTTPException(status_code=404, detail="Тариф не найден")
    if isinstance(e, SubscriptionNotFound):
        return HTTPException(status_code=404, detail="Подписка не найдена")
    if isinstance(e, TooEarlyToRenew):
        return HTTPException(status_code=409, detail="Продление доступно за 3 дня до окончания подписки")
    if isinstance(e, BannedUser):
        return HTTPException(status_code=403, detail="banned")
    if isinstance(e, InsufficientBalance):
        return HTTPException(status_code=402, detail="Недостаточно средств на балансе")
    if isinstance(e, NotEnoughReferralBalance):
        return HTTPException(status_code=402, detail="Недостаточно реферального баланса")
    if isinstance(e, PurchaseInProgress):
        return HTTPException(status_code=409, detail="Покупка уже обрабатывается")
    if isinstance(e, TransactionNotFound):
        return HTTPException(status_code=404, detail="Transaction not found")
    if isinstance(e, PaymentNotConfirmed):
        return HTTPException(status_code=409, detail="Transaction not approved")
    if isinstance(e, PromocodeNotFound):
        return HTTPException(status_code=404, detail="Промокод не найден")
    if isinstance(e, PromocodeAlreadyUsed):
        return HTTPException(status_code=409, detail="Промокод уже использован")
    if isinstance(e, PromocodeExhausted):
        return HTTPException(status_code=409, detail="Лимит активаций промокода исчерпан")
    return HTTPException(status_code=500, detail=str(e) or "Внутренняя ошибка")


async def _get_user(session, user_id: int) -> User:
    user = None
    if _INT32_MIN <= int(user_id) <= _INT32_MAX:
        try:
            user = await session.get(User, user_id)
        except DBAPIError:
            user = None
    if not user:
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if bool(getattr(user, "banned", False)):
        raise HTTPException(status_code=403, detail="banned")
    return user
