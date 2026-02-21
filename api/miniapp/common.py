from __future__ import annotations

from typing import Any, Optional

from aiogram.utils.web_app import safe_parse_webapp_init_data
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.loader import bot, settings
from backend.database.session import async_session
from backend.services import (
    WithdrawalService,
    BillingService,
    DeviceService,
    PromoService,
    ReferralService,
    SubscriptionService,
    TransactionService,
    UserService,
    VPNService,
)
from backend.services.exceptions import (
    NotEnoughReferralBalance,
    DeviceLimitReached,
    DeviceNotFound,
    InsufficientBalance,
    KeyCreationError,
    PaymentNotConfirmed,
    PlanNotFound,
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
if not XRAY_AUTH_TOKEN:
    raise RuntimeError("XRAY_AUTH is not set in settings")

PLATEGA_METHOD_CARD = 11
PLATEGA_METHOD_SBP = 2

BOT_USERNAME = getattr(settings, "BOT_USERNAME", "LunetVPNBot")
SETUP_URL_FALLBACK = getattr(settings, "SETUP_URL", "https://t.me/LunetVPNBot")


class InitPayload(BaseModel):
    initData: Optional[str] = None


class CreateKeyPayload(InitPayload):
    server_id: int
    label: str | None = None


class DeleteKeyPayload(InitPayload):
    key_id: int


class DeleteDevicePayload(InitPayload):
    device_id: int


class BuySubscriptionPayload(InitPayload):
    plan_id: int


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


def _get_tg_user(init_data: Optional[str]) -> dict[str, Any]:
    if not init_data:
        raise HTTPException(401, "initData is missing. �������� ����-���������� �� Telegram.")

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
        raise HTTPException(404, "user not found, ������� ������� � ����")

    if getattr(user, "banned", False):
        raise HTTPException(status_code=403, detail="banned")

    return user


def _map_service_error(e: Exception) -> HTTPException:
    if isinstance(e, InsufficientBalance):
        return HTTPException(status_code=402, detail="������������ ������� �� �������")
    if isinstance(e, NotEnoughReferralBalance):
        return HTTPException(status_code=402, detail="������������ ������������ �������")
    if isinstance(e, PaymentNotConfirmed):
        return HTTPException(status_code=409, detail=str(e) or "������ ��� �� �����������")

    if isinstance(e, PlanNotFound):
        return HTTPException(status_code=404, detail=str(e) or "����� �� ������")
    if isinstance(e, SubscriptionNotFound):
        return HTTPException(status_code=404, detail=str(e) or "�������� �� �������")
    if isinstance(e, TooEarlyToRenew):
        return HTTPException(status_code=409, detail="��������� �������� ������ �� 3 ��� �� ��������� ������� ��������")
    if isinstance(e, UserNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Пользователь не найден")
    if isinstance(e, TransactionNotFound):
        return HTTPException(status_code=404, detail=str(e) or "���������� �� �������")

    if isinstance(e, PromocodeNotFound):
        return HTTPException(status_code=404, detail="�������� �� ������")
    if isinstance(e, PromocodeAlreadyUsed):
        return HTTPException(status_code=409, detail="�������� ��� �����������")
    if isinstance(e, PromocodeExhausted):
        return HTTPException(status_code=409, detail="����� ������������� ��������� ��������")

    if isinstance(e, ServerNotFound):
        return HTTPException(status_code=404, detail="������ �� ������")
    if isinstance(e, KeyCreationError):
        return HTTPException(status_code=500, detail=str(e) or "������ �������� �����")
    if isinstance(e, DeviceNotFound):
        return HTTPException(status_code=404, detail=str(e) or "���������� �� �������")
    if isinstance(e, DeviceLimitReached):
        return HTTPException(status_code=409, detail=str(e) or "��������� ����� ���������")

    return HTTPException(status_code=500, detail=str(e) or "���������� ������")


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
    "DeviceService",
    "PromoService",
    "SubscriptionService",
    "TransactionService",
    "UserService",
    "VPNService",
    "ReferralService",
    "UserNotFound",
    "SubscriptionNotFound",
    "PlanNotFound",
    "TooEarlyToRenew",
    "InsufficientBalance",
    "TransactionNotFound",
    "PaymentNotConfirmed",
    "NotEnoughReferralBalance",
    "PromocodeNotFound",
    "PromocodeAlreadyUsed",
    "PromocodeExhausted",
    "KeyCreationError",
    "ServerNotFound",
    "DeviceNotFound",
    "DeviceLimitReached",
    "BOT_TOKEN",
    "XRAY_AUTH_TOKEN",
    "PLATEGA_METHOD_CARD",
    "PLATEGA_METHOD_SBP",
    "BOT_USERNAME",
    "SETUP_URL_FALLBACK",
    "InitPayload",
    "CreateKeyPayload",
    "DeleteKeyPayload",
    "DeleteDevicePayload",
    "BuySubscriptionPayload",
    "TopupPayload",
    "BalanceCheckPayload",
    "ApplyPromocodePayload",
    "CreateWithdrawalPayload",
    "_get_tg_user",
    "_get_user_or_404",
    "_map_service_error",
]

