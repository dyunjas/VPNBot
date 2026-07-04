from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl

from aiogram.utils.web_app import safe_parse_webapp_init_data
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.loader import bot, settings
from backend.database.session import async_session
from backend.services import (
    WithdrawalService,
    BillingService,
    PromoService,
    ReferralService,
    SubscriptionService,
    TransactionService,
    UserService,
    RemnaWaveService,
)
from backend.services.exceptions import (
    NotEnoughReferralBalance,
    InsufficientBalance,
    KeyCreationError,
    PaymentNotConfirmed,
    PlanNotFound,
    PurchaseInProgress,
    BannedUser,
    PromocodeAlreadyUsed,
    PromocodeExhausted,
    PromocodeNotFound,
    ServerNotFound,
    SubscriptionNotFound,
    TooEarlyToRenew,
    TransactionNotFound,
    UserNotFound,
)

BOT_TOKEN = settings.BOT_TOKEN
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in settings")

XRAY_AUTH_TOKEN = settings.XRAY_AUTH

PLATEGA_METHOD_CARD = 11
PLATEGA_METHOD_SBP = 2

BOT_USERNAME = getattr(settings, "BOT_USERNAME", "LunetVPNBot")
SETUP_URL_FALLBACK = getattr(settings, "SETUP_URL", "https://t.me/LunetVPNBot")
MINIAPP_INITDATA_MAX_AGE_SEC = max(
    60,
    int(getattr(settings, "MINIAPP_INITDATA_MAX_AGE_SEC", 3600) or 3600),
)


class InitPayload(BaseModel):
    initData: Optional[str] = None


class DeleteDevicePayload(InitPayload):
    device_id: int


class BuySubscriptionPayload(InitPayload):
    plan_id: int


class BuyTrafficPayload(InitPayload):
    gb: int


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


def _extract_auth_date(init_data: str) -> int | None:
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
    except ValueError:
        return None

    raw = params.get("auth_date")
    if not raw:
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _get_tg_user(init_data: Optional[str]) -> dict[str, Any]:
    if not init_data:
        raise HTTPException(401, "initData is missing. Откройте мини-приложение из Telegram.")

    auth_date = _extract_auth_date(init_data)
    if auth_date is None:
        raise HTTPException(401, "invalid initData")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if auth_date > now_ts + 60 or (now_ts - auth_date) > MINIAPP_INITDATA_MAX_AGE_SEC:
        raise HTTPException(401, "initData expired. Откройте мини-приложение заново из Telegram.")

    try:
        parsed = safe_parse_webapp_init_data(BOT_TOKEN, init_data)
    except ValueError:
        raise HTTPException(401, "invalid initData signature")

    if not parsed.user:
        raise HTTPException(400, "no user in initData")

    user = parsed.user
    return {
        "id": user.id,
        "username": user.username,
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "photo_url": getattr(user, "photo_url", None),
    }


async def _get_user_or_404(session: AsyncSession, tg_id: int):
    user_service = UserService(session)
    try:
        user = await user_service.get_by_tg_id(tg_id)
    except UserNotFound:
        raise HTTPException(404, "user not found, сначала зайдите в бота")

    if getattr(user, "banned", False):
        raise HTTPException(status_code=403, detail="banned")

    return user


def _map_service_error(e: Exception) -> HTTPException:
    if isinstance(e, HTTPException):
        return e
    if isinstance(e, InsufficientBalance):
        return HTTPException(status_code=409, detail="Недостаточно средств на балансе. Пополните баланс.")
    if isinstance(e, NotEnoughReferralBalance):
        return HTTPException(status_code=402, detail="Недостаточно реферального баланса")
    if isinstance(e, PaymentNotConfirmed):
        return HTTPException(status_code=409, detail="Transaction not approved")
    if isinstance(e, PurchaseInProgress):
        return HTTPException(status_code=409, detail=str(e) or "Покупка уже обрабатывается")
    if isinstance(e, BannedUser):
        return HTTPException(status_code=403, detail="banned")

    if isinstance(e, PlanNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Тариф не найден")
    if isinstance(e, SubscriptionNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Подписка не найдена")
    if isinstance(e, TooEarlyToRenew):
        return HTTPException(status_code=409, detail="Продлить подписку можно только за 3 дня до окончания текущей")
    if isinstance(e, UserNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Пользователь не найден")
    if isinstance(e, TransactionNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Транзакция не найдена")

    if isinstance(e, PromocodeNotFound):
        return HTTPException(status_code=404, detail="Промокод не найден")
    if isinstance(e, PromocodeAlreadyUsed):
        return HTTPException(status_code=409, detail="Промокод уже использован")
    if isinstance(e, PromocodeExhausted):
        return HTTPException(status_code=409, detail="Лимит активаций промокода исчерпан")

    if isinstance(e, ServerNotFound):
        return HTTPException(status_code=404, detail="Сервер не найден")
    if isinstance(e, KeyCreationError):
        return HTTPException(status_code=500, detail=str(e) or "Ошибка создания ключа")
    return HTTPException(status_code=500, detail=str(e) or "Внутренняя ошибка")


__all__ = [
    "Any",
    "Optional",
    "safe_parse_webapp_init_data",
    "APIRouter",
    "HTTPException",
    "BaseModel",
    "AsyncSession",
    "settings",
    "bot",
    "async_session",
    "BillingService",
    "WithdrawalService",
    "PromoService",
    "SubscriptionService",
    "TransactionService",
    "UserService",
    "ReferralService",
    "RemnaWaveService",
    "UserNotFound",
    "SubscriptionNotFound",
    "PlanNotFound",
    "TooEarlyToRenew",
    "InsufficientBalance",
    "PurchaseInProgress",
    "TransactionNotFound",
    "PaymentNotConfirmed",
    "NotEnoughReferralBalance",
    "PromocodeNotFound",
    "PromocodeAlreadyUsed",
    "PromocodeExhausted",
    "KeyCreationError",
    "ServerNotFound",
    "BOT_TOKEN",
    "XRAY_AUTH_TOKEN",
    "PLATEGA_METHOD_CARD",
    "PLATEGA_METHOD_SBP",
    "BOT_USERNAME",
    "SETUP_URL_FALLBACK",
    "InitPayload",
    "DeleteDevicePayload",
    "BuySubscriptionPayload",
    "BuyTrafficPayload",
    "TopupPayload",
    "BalanceCheckPayload",
    "ApplyPromocodePayload",
    "CreateWithdrawalPayload",
    "_get_tg_user",
    "_get_user_or_404",
    "_map_service_error",
]
