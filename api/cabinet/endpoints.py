from __future__ import annotations

import secrets
import smtplib
import time
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.core.loader import bot
from backend.database.models import User
from backend.database.session import async_session
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

router = APIRouter(prefix="/cabinet-api", tags=["cabinet"])
JWT_ALG = "HS256"
OTP_TTL_SEC = 600
ACCESS_TTL_MIN = 30
REFRESH_TTL_DAYS = 30
REFRESH_COOKIE = "cabinet_refresh_token"

_OTP_STORE: dict[str, dict] = {}
_OTP_LAST_SENT: dict[str, float] = {}
_OTP_SEND_COOLDOWN_SEC = 30


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
    pass


class DeleteDevicePayload(BaseModel):
    device_id: int


class BuySubscriptionPayload(BaseModel):
    plan_id: int


class BuyTrafficPayload(BaseModel):
    gb: int


class TopupPayload(BaseModel):
    amount: int
    method: str = "platega"
    asset: str = "USDT"
    platega_type: str = "card"


class BalanceCheckPayload(BaseModel):
    method: str = "platega"
    provider_id: str | None = None


class ApplyPromocodePayload(BaseModel):
    code: str


class CreateWithdrawalPayload(BaseModel):
    amount: int
    method: str


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
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return payload


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
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _otp_key(channel: str, identity: str) -> str:
    return f"{channel}:{identity.strip().lower()}"


def _cleanup_otp() -> None:
    now = int(time.time())
    stale = [k for k, v in _OTP_STORE.items() if int(v.get("expires_at", 0)) < now]
    for k in stale:
        _OTP_STORE.pop(k, None)


def _put_otp(channel: str, identity: str, user_id: int, code: str) -> None:
    _cleanup_otp()
    key = _otp_key(channel, identity)
    _OTP_STORE[key] = {
        "user_id": user_id,
        "code": code,
        "expires_at": int(time.time()) + OTP_TTL_SEC,
    }
    _OTP_LAST_SENT[key] = time.time()


def _otp_send_allowed(channel: str, identity: str) -> bool:
    key = _otp_key(channel, identity)
    last_sent = float(_OTP_LAST_SENT.get(key, 0) or 0)
    return (time.time() - last_sent) >= _OTP_SEND_COOLDOWN_SEC


def _pop_otp(channel: str, identity: str, code: str) -> int | None:
    _cleanup_otp()
    key = _otp_key(channel, identity)
    rec = _OTP_STORE.get(key)
    if not rec:
        return None
    if str(rec.get("code")) != str(code).strip():
        return None
    _OTP_STORE.pop(key, None)
    return int(rec.get("user_id"))


def _smtp_send_code(email: str, code: str) -> None:
    host = (os.getenv("SMTP_HOST") or getattr(settings, "SMTP_HOST", None) or "").strip()
    user = (os.getenv("SMTP_USER") or getattr(settings, "SMTP_USER", None) or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or getattr(settings, "SMTP_PASSWORD", None) or "").strip()
    from_email = (os.getenv("SMTP_FROM_EMAIL") or getattr(settings, "SMTP_FROM_EMAIL", None) or user or "").strip()
    raw_port = os.getenv("SMTP_PORT") or str(getattr(settings, "SMTP_PORT", 587) or 587)
    port = int(str(raw_port).strip() or 587)
    if not host or not from_email:
        logger.error(
            "[cabinet][smtp] not configured host=%r from_email=%r user=%r port=%r",
            host,
            from_email,
            user,
            raw_port,
        )
        raise HTTPException(status_code=503, detail="SMTP is not configured")

    msg = EmailMessage()
    msg["Subject"] = "Lunet cabinet login code"
    msg["From"] = from_email
    msg["To"] = email
    msg.set_content(f"Ваш код входа: {code}\nКод действует {OTP_TTL_SEC // 60} минут.")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            if user:
                server.login(user, password)
            server.send_message(msg)
    else:
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
    if isinstance(e, PurchaseInProgress):
        return HTTPException(status_code=409, detail="Покупка уже обрабатывается")
    if isinstance(e, TransactionNotFound):
        return HTTPException(status_code=404, detail="Transaction not found")
    if isinstance(e, PaymentNotConfirmed):
        return HTTPException(status_code=409, detail="Платеж еще не подтвержден")
    if isinstance(e, PromocodeNotFound):
        return HTTPException(status_code=404, detail="Промокод не найден")
    if isinstance(e, PromocodeAlreadyUsed):
        return HTTPException(status_code=409, detail="Промокод уже использован")
    if isinstance(e, PromocodeExhausted):
        return HTTPException(status_code=409, detail="Лимит активаций промокода исчерпан")
    return HTTPException(status_code=500, detail=str(e) or "Внутренняя ошибка")


async def _get_user(session, user_id: int) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if bool(getattr(user, "banned", False)):
        raise HTTPException(status_code=403, detail="banned")
    return user


@router.post("/auth/register")
async def cabinet_register(payload: RegisterPayload):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    tg_user = _get_tg_user(payload.initData)
    tg_id = int(tg_user["id"])

    async with async_session() as session:
        existing_email = await session.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="email already registered")

        existing_tg = await session.execute(select(User).where(User.tg_id == tg_id))
        user = existing_tg.scalar_one_or_none()
        if user:
            user.email = email
        else:
            user = User(
                tg_id=tg_id,
                email=email,
                username=None,
                balance=0,
                banned=False,
            )
            session.add(user)
        await session.commit()
        await session.refresh(user)

    code = f"{secrets.randbelow(1000000):06d}"
    _put_otp("email", email, user.id, code)
    _smtp_send_code(email, code)
    return {"ok": True, "message": "verification code sent"}


@router.post("/auth/send-email-code")
async def cabinet_send_email_code(payload: SendEmailCodePayload):
    email = payload.email.strip().lower()
    async with async_session() as session:
        res = await session.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user with this email not found")
    if not _otp_send_allowed("email", email):
        raise HTTPException(status_code=429, detail="code already sent recently")

    code = f"{secrets.randbelow(1000000):06d}"
    _put_otp("email", email, user.id, code)
    _smtp_send_code(email, code)
    return {"ok": True}


@router.post("/auth/send-telegram-code")
async def cabinet_send_telegram_code(payload: SendTelegramCodePayload):
    async with async_session() as session:
        res = await session.execute(select(User).where(User.tg_id == payload.tg_id))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user with this tg_id not found")
    if not _otp_send_allowed("telegram", str(payload.tg_id)):
        raise HTTPException(status_code=429, detail="code already sent recently")

    code = f"{secrets.randbelow(1000000):06d}"
    _put_otp("telegram", str(payload.tg_id), user.id, code)
    runtime_bot = bot
    if runtime_bot is not None:
        await runtime_bot.send_message(chat_id=payload.tg_id, text=f"<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji>Код входа в кабинет: <code>{code}</code>", parse_mode="HTML")
        return {"ok": True}

    bot_token = (settings.BOT_TOKEN or "").strip()
    if not bot_token:
        raise HTTPException(status_code=503, detail="BOT_TOKEN is not configured")

    proxy_url = (settings.BOT_PROXY or "").strip() or None
    session = AiohttpSession(proxy=proxy_url) if proxy_url else AiohttpSession()
    temp_bot = Bot(token=bot_token, session=session)
    try:
        await temp_bot.send_message(chat_id=payload.tg_id, text=f"<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji>Код входа в кабинет: <code>{code}</code>", parse_mode="HTML")
    finally:
        await temp_bot.session.close()
    return {"ok": True}


@router.post("/auth/verify-code")
async def cabinet_verify_code(payload: VerifyCodePayload):
    if payload.channel == "email":
        identity = (payload.email or "").strip().lower()
        if not identity:
            raise HTTPException(status_code=400, detail="email is required")
        user_id = _pop_otp("email", identity, payload.code)
    else:
        if payload.tg_id is None:
            raise HTTPException(status_code=400, detail="tg_id is required")
        identity = str(payload.tg_id)
        user_id = _pop_otp("telegram", identity, payload.code)

    if not user_id:
        raise HTTPException(status_code=400, detail="invalid or expired code")
    access_token = _create_access_token(user_id)
    refresh_token = _create_refresh_token(user_id)
    response = JSONResponse({"ok": True, "access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=str(settings.PUBLIC_BASE_URL or "").strip().startswith("https://"),
        samesite="lax",
        max_age=REFRESH_TTL_DAYS * 24 * 3600,
        path="/",
    )
    return response


@router.post("/auth/refresh")
async def cabinet_refresh(request: Request):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = _decode_token(refresh_token)
    if payload.get("scope") != "cabinet:refresh":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    access_token = _create_access_token(user_id)
    return {"ok": True, "access_token": access_token, "token_type": "bearer"}


@router.post("/auth/logout")
async def cabinet_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(key=REFRESH_COOKIE, path="/")
    return response


@router.get("/auth/me")
async def cabinet_auth_me(user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        return {"ok": True, "user": {"id": user.id, "tg_id": user.tg_id, "email": user.email, "username": user.username}}


@router.post("/profile")
async def cabinet_profile(_: InitPayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        tx_service = TransactionService(session)
        referral_service = ReferralService(session)
        txs = (await tx_service.list_by_user(user.id))[:50]
        referral_account = await referral_service.get_account(user.id)
        if not referral_account:
            referral_account = await referral_service.create_account(user.id)
            await session.commit()
        return {
            "ok": True,
            "user": {"tg_id": user.tg_id, "username": user.username, "balance": user.balance, "email": user.email, "created_at": user.created_at.isoformat() if user.created_at else None},
            "referral": {"balance": int(referral_account.referral_balance or 0), "percent": int(referral_account.referral_percent or 0), "invited_count": int(referral_account.invited_count or 0)},
            "transactions": [
                {
                    "id": t.id,
                    "amount": int(t.amount) if t.amount is not None else None,
                    "payment_system": t.payment_system,
                    "order_id": getattr(t, "order_id", None),
                    "paid": t.paid,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "paid_at": t.paid_at.isoformat() if t.paid_at else None,
                    "transaction_id": getattr(t, "transaction_id", None),
                }
                for t in txs
            ],
        }


@router.post("/status")
async def cabinet_status(_: InitPayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        sub_service = SubscriptionService(session)
        remnawave_service = RemnaWaveService(session)
        try:
            active_sub = await sub_service.get_active_subscription(user_id=user.id)
        except SubscriptionNotFound:
            return {"ok": True, "has_subscription": False, "statusText": "Нет активной подписки.", "active_keys": 0, "subscription_url": None}

        remote = await remnawave_service.get_user_snapshot(user=user)
        if not isinstance(remote, dict):
            return {"ok": True, "has_subscription": False, "statusText": "Нет активной подписки.", "active_keys": 0, "subscription_url": None}
        status = str(remote.get("status") or "")
        expire_at = remote.get("expireAt")
        sub_url = remote.get("subscriptionUrl") or remote.get("subscription_url")
        devices = await remnawave_service.get_user_hwid_devices(user=user)
        try:
            devices_limit = max(0, int(remote.get("hwidDeviceLimit"))) if remote.get("hwidDeviceLimit") is not None else 0
        except Exception:
            devices_limit = 0
        user_traffic = remote.get("userTraffic") if isinstance(remote.get("userTraffic"), dict) else {}
        return {
            "ok": True,
            "has_subscription": status in {"ACTIVE", "LIMITED"},
            "statusText": f"Статус: {status or 'UNKNOWN'}\nДействует до: {expire_at or '—'}",
            "active_keys": 0,
            "subscription_url": sub_url,
            "plan": None,
            "subscription": {
                "current_period_start": None,
                "current_period_end": expire_at,
                "status": status or None,
                "token": getattr(active_sub, "subscription_token", None),
                "gb_left": None,
                "devices_limit": devices_limit,
                "devices_used": len(devices),
                "devices_left": max(devices_limit - len(devices), 0) if devices_limit > 0 else None,
            },
            "remnawave": {
                "uuid": remote.get("uuid"),
                "id": remote.get("id"),
                "username": remote.get("username"),
                "trafficLimitBytes": remote.get("trafficLimitBytes"),
                "trafficLimitStrategy": remote.get("trafficLimitStrategy"),
                "usedTrafficBytes": user_traffic.get("usedTrafficBytes"),
                "lifetimeUsedTrafficBytes": user_traffic.get("lifetimeUsedTrafficBytes"),
                "hwidDeviceLimit": remote.get("hwidDeviceLimit"),
            },
        }


@router.post("/plans")
async def cabinet_plans(_: InitPayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        _ = await _get_user(session, user_id)
        plans = await SubscriptionService(session).list_plans()
        return {"ok": True, "plans": [{"id": p.id, "name": p.name, "price": p.price, "period_days": p.period_days, "gb_limit": int(getattr(p, "gb_limit", 0) or 0), "created_at": p.created_at.isoformat() if p.created_at else None} for p in plans]}


@router.post("/subscription/buy")
async def cabinet_subscription_buy(payload: BuySubscriptionPayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        billing = BillingService(session)
        try:
            sub = await billing.buy_subscription(user_id=user.id, plan_id=payload.plan_id, auto_renew=True)
        except Exception as e:
            raise _map_service_error(e)
        plan = await SubscriptionService(session).get_plan(sub.plan_id)
        return {"ok": True, "subscription": {"id": sub.id, "plan_id": plan.id, "plan_name": plan.name, "current_period_start": sub.current_period_start.isoformat(), "current_period_end": sub.current_period_end.isoformat(), "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status)}}


@router.post("/subscription/traffic/buy")
async def cabinet_subscription_traffic_buy(payload: BuyTrafficPayload, user_id: int = Depends(require_cabinet_auth)):
    if payload.gb <= 0:
        raise HTTPException(status_code=400, detail="Введите количество ГБ больше 0")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        billing = BillingService(session)
        try:
            sub, charged = await billing.add_gb_to_subscription(user_id=user.id, gb=int(payload.gb))
        except Exception as e:
            raise _map_service_error(e)
        return {"ok": True, "subscription_id": sub.id, "gb_added": int(payload.gb), "charged": int(charged)}


@router.post("/devices")
async def cabinet_devices(_: InitPayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        devices = await RemnaWaveService(session).get_user_hwid_devices(user=user)
        return {"ok": True, "items": [{"id": i, "hwid": d.get("hwid"), "device_model": d.get("deviceModel"), "device_os": d.get("platform"), "os_version": d.get("osVersion"), "device_locale": None, "user_agent": d.get("userAgent"), "first_seen_at": d.get("createdAt"), "last_seen_at": d.get("updatedAt")} for i, d in enumerate(devices)]}


@router.post("/device/delete")
async def cabinet_device_delete(payload: DeleteDevicePayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        remn = RemnaWaveService(session)
        devices = await remn.get_user_hwid_devices(user=user)
        if payload.device_id < 0 or payload.device_id >= len(devices):
            raise HTTPException(status_code=404, detail="device not found")
        hwid = str(devices[payload.device_id].get("hwid") or "").strip()
        if not hwid:
            raise HTTPException(status_code=404, detail="device not found")
        if not await remn.delete_hwid_device(user=user, hwid=hwid):
            raise HTTPException(status_code=502, detail="remnawave delete device failed")
        return {"ok": True, "deleted_device_id": payload.device_id}


@router.post("/referral/info")
async def cabinet_referral_info(_: InitPayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        service = ReferralService(session)
        account = await service.get_account(user.id)
        if not account:
            account = await service.create_account(user.id)
            await session.commit()
        referral_url = f"https://t.me/{getattr(settings, 'BOT_USERNAME', 'LunetVPNBot')}?start=ref_{user.tg_id}"
        return {"ok": True, "referral_url": referral_url, "referral": {"invited_count": int(account.invited_count or 0), "balance": int(account.referral_balance or 0), "percent": int(account.referral_percent or 0)}}


@router.post("/referral/withdrawals")
async def cabinet_referral_withdrawals(_: InitPayload, user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        rows = await WithdrawalService(session).list_by_user(user_id=user.id, limit=20)
        return {"ok": True, "items": [{"id": w.id, "amount": int(w.amount), "method": w.method, "status": w.status.value if w.status else None, "created_at": w.created_at.isoformat() if w.created_at else None} for w in rows]}


@router.post("/referral/withdraw")
async def cabinet_referral_withdraw(payload: CreateWithdrawalPayload, user_id: int = Depends(require_cabinet_auth)):
    amount = int(payload.amount or 0)
    method = (payload.method or "").strip()
    if amount < 500:
        raise HTTPException(400, "Минимальная сумма вывода: 500 RUB")
    if len(method) < 8:
        raise HTTPException(400, "Укажите способ вывода и реквизиты получателя")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        try:
            wd = await WithdrawalService(session).create_withdrawal(user_id=user.id, amount=amount, method=method)
        except Exception as e:
            raise _map_service_error(e)
        return {"ok": True, "withdrawal": {"id": wd.id, "amount": int(wd.amount), "method": wd.method, "status": wd.status.value if wd.status else None, "created_at": wd.created_at.isoformat() if wd.created_at else None}, "message": "Заявка на вывод создана и передана на обработку"}


@router.post("/promocode/apply")
async def cabinet_promocode_apply(payload: ApplyPromocodePayload, user_id: int = Depends(require_cabinet_auth)):
    code = (payload.code or "").strip()
    if not code:
        raise HTTPException(400, "Введите промокод")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        promo_service = PromoService(session)
        user_service = UserService(session)
        try:
            promo = await promo_service.activate_promocode(user_id=user.id, code=code)
        except Exception as e:
            raise _map_service_error(e)
        fresh_user = await user_service.get_by_id(user.id)
        return {"ok": True, "amount_added": int(promo.amount or 0), "balance": fresh_user.balance}


@router.post("/balance/topup")
async def cabinet_balance_topup(payload: TopupPayload, user_id: int = Depends(require_cabinet_auth)):
    if payload.amount <= 0:
        raise HTTPException(400, "Сумма должна быть больше нуля")
    method = (payload.method or "platega").lower().strip()
    if method not in ("platega", "crypto", "pally"):
        raise HTTPException(400, "Неверный способ оплаты")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        billing = BillingService(session)
        try:
            if method == "platega":
                pl_type = (payload.platega_type or "card").lower().strip()
                if pl_type not in ("card", "sbp"):
                    raise HTTPException(400, "Выберите карту или СБП")
                payment = await billing.create_platega_payment(
                    user_id=user.id,
                    amount=float(payload.amount),
                    payment_method=11 if pl_type == "card" else 2,
                    description=f"Пополнение баланса на {payload.amount} RUB",
                    return_url="https://t.me/LunetVPNBot",
                    failed_url="https://t.me/LunetVPNBot",
                )
                return {"ok": True, "method": "platega", "platega_type": pl_type, "payment_url": payment.get("redirect") or payment.get("payformSuccessUrl") or payment.get("payment_url"), "provider_id": str(payment.get("id") or payment.get("transactionId") or ""), "status": payment.get("status")}
            if method == "pally":
                payment = await billing.create_pally_payment(
                    user_id=user.id,
                    amount=float(payload.amount),
                    description=f"Пополнение баланса на {payload.amount} RUB",
                    return_url="https://t.me/LunetVPNBot",
                    failed_url="https://t.me/LunetVPNBot",
                )
                return {"ok": True, "method": "pally", "payment_url": payment.get("payment_url") or payment.get("pay_url") or payment.get("url") or payment.get("link") or payment.get("redirect"), "provider_id": str(payment.get("id") or ""), "status": payment.get("status")}
            invoice = await billing.create_crypto_invoice(
                user_id=user.id,
                amount_rub=int(payload.amount),
                asset=(payload.asset or "USDT"),
                description=f"Пополнение баланса на {payload.amount} RUB",
                expires_in=900,
            )
            return {"ok": True, "method": "crypto", "payment_url": invoice.get("pay_url") or invoice.get("bot_invoice_url") or invoice.get("mini_app_invoice_url") or invoice.get("web_app_invoice_url") or invoice.get("url"), "provider_id": str(invoice.get("invoice_id")) if invoice.get("invoice_id") is not None else None, "status": invoice.get("status"), "asset": payload.asset or "USDT"}
        except HTTPException:
            raise
        except Exception as e:
            raise _map_service_error(e)


@router.post("/balance/check")
async def cabinet_balance_check(payload: BalanceCheckPayload, user_id: int = Depends(require_cabinet_auth)):
    method = (payload.method or "platega").lower().strip()
    if method not in ("platega", "crypto", "pally"):
        raise HTTPException(400, "method must be 'platega', 'crypto' or 'pally'")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        billing = BillingService(session)
        tx_service = TransactionService(session)
        user_service = UserService(session)
        provider_id = (payload.provider_id or "").strip() or None
        if not provider_id:
            payment_system = "platega" if method == "platega" else ("PALLY" if method == "pally" else "cryptobot")
            tx = await tx_service.get_last_unpaid_by_system(user_id=user.id, payment_system=payment_system)
            if not tx:
                return {"ok": False, "reason": "no_pending", "message": "Нет незавершенных платежей"}
            provider_id = tx.transaction_id
        try:
            if method == "platega":
                await billing.confirm_platega_payment(provider_id)
            elif method == "pally":
                await billing.confirm_pally_payment(provider_id)
            else:
                await billing.confirm_crypto_payment(int(provider_id))
        except PaymentNotConfirmed:
            try:
                tx = await tx_service.get_by_provider_id(provider_id)
            except TransactionNotFound:
                return {"ok": False, "reason": "tx_not_found", "message": "Transaction not found"}
            fresh_user = await user_service.get_by_id(user.id)
            return {"ok": True, "confirmed": False, "method": method, "transaction": {"id": tx.id, "provider_id": tx.transaction_id, "amount": int(tx.amount) if tx.amount is not None else None, "paid": tx.paid, "status_raw": "NOT_CONFIRMED"}, "balance": fresh_user.balance}
        except TransactionNotFound:
            return {"ok": False, "reason": "tx_not_found", "message": "Transaction not found"}
        except Exception as e:
            raise _map_service_error(e)
        tx = await tx_service.get_by_provider_id(provider_id)
        fresh_user = await user_service.get_by_id(user.id)
        return {"ok": True, "confirmed": True, "method": method, "transaction": {"id": tx.id, "provider_id": tx.transaction_id, "amount": int(tx.amount) if tx.amount is not None else None, "paid": True, "status_raw": "CONFIRMED"}, "balance": fresh_user.balance}
