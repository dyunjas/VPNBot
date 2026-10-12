from __future__ import annotations

import os
import secrets
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Literal

# Shared imports below are also explicitly re-exported to cabinet route modules.
from aiogram import Bot
from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse
import jwt
from jwt.exceptions import PyJWTError as JWTError
from pydantic import BaseModel as PydanticBaseModel, ConfigDict, Field
from sqlalchemy import select

from api.miniapp.common import _get_tg_user
from backend.core.config import settings
from backend.core.loader import bot
from backend.core.logger_config import logger
from backend.database.models import User
from backend.database.models import SecurityRecord
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

_OTP_SEND_COOLDOWN_SEC = 30
_OTP_TG_LOGIN_WINDOW_SEC = 600
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")


class SendEmailCodePayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    tg_id: int | None = None


class SendTelegramCodePayload(BaseModel):
    tg_id: int


class VerifyCodePayload(BaseModel):
    channel: Literal["email", "telegram"]
    email: str | None = None
    tg_id: int | None = None
    code: str = Field(min_length=4, max_length=8)


class RegisterPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    offer_accepted: bool = False
    terms_accepted: bool = False
    privacy_accepted: bool = False


class CompleteRegistrationPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6)


class InitPayload(BaseModel):
    initData: str | None = Field(default=None, max_length=16384)


class DeleteDevicePayload(InitPayload):
    device_id: int


class BuySubscriptionPayload(InitPayload):
    plan_id: int


class BuyTrafficPayload(InitPayload):
    gb: int = Field(ge=1, le=100000)


class BuyDeviceSlotsPayload(InitPayload):
    slots: int = Field(ge=1, le=20)


class SetAutoRenewPayload(InitPayload):
    auto_renew: bool


class GiftSubscriptionPayload(InitPayload):
    plan_id: int
    recipient: str = Field(min_length=1, max_length=320)


class TopupPayload(InitPayload):
    amount: int
    method: str = "platega"
    asset: str = "USDT"
    platega_type: str = "card"


class BalanceCheckPayload(InitPayload):
    method: str = "platega"
    provider_id: str | None = None


class ApplyPromocodePayload(InitPayload):
    code: str = Field(min_length=1, max_length=128)


class CreateWithdrawalPayload(InitPayload):
    amount: int
    method: str


class ReferralTransferPayload(InitPayload):
    amount: int


def _jwt_secret() -> str:
    secret = (settings.SECRET_KEY or "").strip()
    if len(secret) < 32 or secret.startswith(("-----BEGIN", "ssh-")):
        raise HTTPException(status_code=503, detail="Security configuration is incomplete")
    return secret


def _create_access_token(user_id: int, session_id: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "scope": "cabinet:web",
        "iss": "lunet", "aud": "lunet:cabinet", "kind": "access", "jti": secrets.token_urlsafe(24), "sid": session_id or secrets.token_urlsafe(32),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)


def _create_refresh_token(user_id: int, session_id: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "scope": "cabinet:refresh",
        "iss": "lunet", "aud": "lunet:cabinet", "kind": "refresh", "jti": secrets.token_urlsafe(24), "sid": session_id or secrets.token_urlsafe(32),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)


def _decode_token(token: str) -> dict:
    try:
        if len(token) > 4096:
            raise JWTError("Token is too long")
        header = jwt.get_unverified_header(token)
        if header.get("alg") != JWT_ALG or any(name in header for name in ("kid", "jku", "jwk", "x5u", "crit")):
            raise JWTError("Invalid token header")
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALG], audience="lunet:cabinet", issuer="lunet", options={"require": ["exp", "iat", "sub", "aud", "iss"]})
        if any(not isinstance(payload.get(name), str) or not 1 <= len(payload[name]) <= 128 for name in ("sid", "jti")) or payload.get("scope") != {"access": "cabinet:web", "refresh": "cabinet:refresh"}.get(payload.get("kind")):
            raise JWTError("Invalid token claims")
        if any(type(payload.get(name)) is not int for name in ("iat", "exp")):
            raise JWTError("Invalid token timestamps")
        if payload["iat"] > int(time.time()) + 60 or payload["exp"] <= payload["iat"]:
            raise JWTError("Invalid token lifetime")
        return payload
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
    if payload.get("scope") != "cabinet:web" or payload.get("kind") != "access":
        raise HTTPException(status_code=401, detail="Unauthorized")
    await _validate_user_session(payload)
    try:
        return int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


async def _validate_user_session(payload: dict) -> None:
    import hashlib
    key = "cabinet-session:" + hashlib.sha256(str(payload.get("sid", "")).encode()).hexdigest()
    async with async_session() as db:
        record = await db.get(SecurityRecord, key)
        if not record or record.kind != "cabinet_session" or record.expires_at <= int(time.time()) or str(record.data.get("user_id")) != str(payload.get("sub")):
            raise HTTPException(401, "Unauthorized")


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
    if payload.get("scope") != "cabinet:web" or payload.get("kind") != "access":
        raise HTTPException(status_code=401, detail="Unauthorized")
    await _validate_user_session(payload)
    try:
        return int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


async def _resolve_request_user_id(init_data: str | None, user_id: int | None) -> int:
    if user_id is not None:
        return user_id
    tg_user = _get_tg_user(init_data)
    # Telegram IDs and database IDs are distinct namespaces; never fall back
    # to a primary-key lookup using a signed Telegram ID.
    async with async_session() as db:
        user = await db.scalar(select(User).where(User.tg_id == int(tg_user["id"])))
        if not user:
            raise HTTPException(404, "user not found")
        if user.banned:
            raise HTTPException(403, "banned")
        return user.id


from backend.services.one_time_codes import (
    put as _put_otp, allowed as _otp_send_allowed, retry_after as _otp_send_retry_after,
    consume as _consume_otp, pop as _pop_otp,
)


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

    html_body, plain_body = render_code_email(code, purpose=purpose, ttl_seconds=OTP_TTL_SEC)
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
    if isinstance(e, HTTPException):
        return e
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
    return HTTPException(status_code=500, detail="Внутренняя ошибка")


async def _get_user(session, user_id: int) -> User:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if bool(getattr(user, "banned", False)):
        raise HTTPException(status_code=403, detail="banned")
    return user
