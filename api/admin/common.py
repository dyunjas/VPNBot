from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from aiogram.types.input_file import BufferedInputFile
from fastapi import APIRouter, Cookie, Depends, File, Form, Header, HTTPException, Query, UploadFile
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, delete, desc, func, literal, or_, select, update

from backend.core.config import settings
from backend.database.models import (
    BroadcastHistory,
    BroadcastJobStatus,
    PartnerAttribution,
    PartnerLink,
    Promocode,
    PromocodeActivation,
    ReferralAccount,
    ReferralWithdrawal,
    SubStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionTopup,
    Transaction,
    UserActivity,
    User,
    WithdrawalStatus,
)
from backend.database.session import async_session
from backend.services.exceptions import (
    BannedUser,
    InsufficientBalance,
    SubscriptionNotFound,
    UserNotFound,
)
from backend.services.subscription_service import SubscriptionService
from backend.services.activity_service import ActivityService
from backend.services.user_service import UserService
from backend.services.remnawave_service import RemnaWaveService
from backend.services.partner_service import PartnerService

router = APIRouter(prefix="/api/admin", tags=["admin-web"])

SORT_FIELDS = {
    "id": User.id,
    "tg_id": User.tg_id,
    "username": User.username,
    "balance": User.balance,
    "created_at": User.created_at,
    "updated_at": User.updated_at,
}
SUB_SORT_FIELDS = {
    "id": Subscription.id,
    "user_id": Subscription.user_id,
    "status": Subscription.status,
    "current_period_end": Subscription.current_period_end,
    "created_at": Subscription.created_at,
}
TX_SORT_FIELDS = {
    "id": Transaction.id,
    "amount": Transaction.amount,
    "created_at": Transaction.created_at,
    "paid_at": Transaction.paid_at,
}
PLAN_SORT_FIELDS = {
    "id": SubscriptionPlan.id,
    "display_order": SubscriptionPlan.display_order,
    "name": SubscriptionPlan.name,
    "price": SubscriptionPlan.price,
    "period_days": SubscriptionPlan.period_days,
    "purchase_limit": SubscriptionPlan.purchase_limit,
    "is_hidden": SubscriptionPlan.is_hidden,
    "is_trial": SubscriptionPlan.is_trial,
    "created_at": SubscriptionPlan.created_at,
}

JWT_ALG = "HS256"


def _extract_token(auth_header: str | None, x_admin_token: str | None) -> str | None:
    if x_admin_token:
        return x_admin_token.strip()
    if not auth_header:
        return None
    raw = auth_header.strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip() or None
    return raw or None


def _to_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _as_aware_utc(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _http_404_if_none(value, message: str):
    if not value:
        raise HTTPException(status_code=404, detail=message)
    return value


def _jwt_secret() -> str:
    return (settings.SECRET_KEY or "").strip()


def _create_admin_access_token(login: str) -> str:
    secret = _jwt_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="SECRET_KEY is not configured")
    hours = int(settings.ADMIN_WEB_JWT_EXPIRE_HOURS or 12)
    expire_at = datetime.now(timezone.utc) + timedelta(hours=max(hours, 1))
    payload = {
        "sub": login,
        "scope": "admin:web",
        "exp": int(expire_at.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


def _decode_admin_access_token(token: str) -> dict:
    secret = _jwt_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="SECRET_KEY is not configured")
    try:
        return jwt.decode(token, secret, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def require_admin_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    admin_access_token: str | None = Cookie(default=None, alias="admin_access_token"),
) -> dict:
    token = _extract_token(authorization, x_admin_token) or (admin_access_token or "").strip() or None
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = _decode_admin_access_token(token)
    if payload.get("scope") != "admin:web":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return payload


class LoginPayload(BaseModel):
    login: str
    password: str


class UserActionPayload(BaseModel):
    action: Literal[
        "ban",
        "unban",
        "add_balance",
        "sub_balance",
        "add_traffic",
    ]
    amount: int | None = None
    gb: float | None = Field(default=None, gt=0)


class SubscriptionCreatePayload(BaseModel):
    user_id: int
    plan_id: int
    auto_renew: bool = False


class SubscriptionUpdatePayload(BaseModel):
    plan_id: int | None = None
    status: Literal["active", "past_due", "expired", "canceled"] | None = None
    auto_renew: bool | None = None
    device_limit: int | None = Field(default=None, ge=0)
    extend_days: int | None = None
    current_period_end: datetime | None = None


class SubscriptionBulkExtendPayload(BaseModel):
    target: Literal["all", "active", "inactive"]
    days: int = Field(gt=0, le=3650)


class SubscriptionTrafficPayload(BaseModel):
    gb: float = Field(gt=0)


class PlanCreatePayload(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    price: int = Field(gt=0)
    period_days: int = Field(default=30, gt=0)
    gb_limit: int = Field(default=100, ge=0)
    device_limit: int = Field(default=3, ge=0)
    purchase_limit: int = Field(default=0, ge=0)
    is_hidden: bool = False
    is_trial: bool = False


class PlanUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=64)
    price: int | None = Field(default=None, gt=0)
    period_days: int | None = Field(default=None, gt=0)
    gb_limit: int | None = Field(default=None, ge=0)
    device_limit: int | None = Field(default=None, ge=0)
    display_order: int | None = Field(default=None, ge=0)
    purchase_limit: int | None = Field(default=None, ge=0)
    is_hidden: bool | None = None
    is_trial: bool | None = None


class PlanMovePayload(BaseModel):
    direction: Literal["up", "down"]


class PromocodeCreatePayload(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    amount: int = Field(gt=0)
    usages: int = Field(default=1, gt=0)


class PartnerLinkCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str | None = Field(default=None, min_length=3, max_length=64)


class PartnerLinkUpdatePayload(BaseModel):
    is_active: bool


__all__ = [
    "asyncio",
    "uuid",
    "datetime",
    "timedelta",
    "timezone",
    "Literal",
    "BufferedInputFile",
    "APIRouter",
    "Depends",
    "Cookie",
    "File",
    "Form",
    "Header",
    "HTTPException",
    "Query",
    "UploadFile",
    "JWTError",
    "jwt",
    "BaseModel",
    "Field",
    "String",
    "cast",
    "delete",
    "desc",
    "func",
    "literal",
    "or_",
    "select",
    "update",
    "settings",
    "BroadcastHistory",
    "BroadcastJobStatus",
    "PartnerAttribution",
    "PartnerLink",
    "Promocode",
    "PromocodeActivation",
    "ReferralAccount",
    "ReferralWithdrawal",
    "SubStatus",
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionTopup",
    "Transaction",
    "UserActivity",
    "User",
    "WithdrawalStatus",
    "async_session",
    "InsufficientBalance",
    "BannedUser",
    "SubscriptionNotFound",
    "UserNotFound",
    "SubscriptionService",
    "ActivityService",
    "UserService",
    "RemnaWaveService",
    "PartnerService",
    "SORT_FIELDS",
    "SUB_SORT_FIELDS",
    "TX_SORT_FIELDS",
    "PLAN_SORT_FIELDS",
    "JWT_ALG",
    "_extract_token",
    "_to_iso",
    "_as_aware_utc",
    "_http_404_if_none",
    "_jwt_secret",
    "_create_admin_access_token",
    "_decode_admin_access_token",
    "require_admin_auth",
    "LoginPayload",
    "UserActionPayload",
    "SubscriptionCreatePayload",
    "SubscriptionUpdatePayload",
    "SubscriptionBulkExtendPayload",
    "SubscriptionTrafficPayload",
    "PlanCreatePayload",
    "PlanUpdatePayload",
    "PlanMovePayload",
    "PromocodeCreatePayload",
    "PartnerLinkCreatePayload",
    "PartnerLinkUpdatePayload",
]
