from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from aiogram.types.input_file import BufferedInputFile
from fastapi import APIRouter, Cookie, Depends, File, Form, Header, HTTPException, Query, UploadFile, Request
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


async def require_admin_auth(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    admin_access_token: str | None = Cookie(default=None, alias="admin_access_token"),
) -> dict:
    from backend.services.admin_security import validate_session, require_fresh
    payload = await validate_session(request)
    if "/export/" in request.url.path or request.url.path.endswith("/download"):
        require_fresh(payload)
        from backend.services.admin_security import rate_limit
        await rate_limit(request, "admin-export", payload["owner"], maximum=5, window=60)
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.url.path.startswith("/api/admin/auth/"):
        require_fresh(payload)
    return payload


async def require_superadmin_auth(auth=Depends(require_admin_auth)) -> dict:
    role = auth.get("role")
    if role != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return auth


async def require_support_auth(auth=Depends(require_admin_auth)) -> dict:
    role = auth.get("role")
    if role not in {"superadmin", "support"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    return auth


class LoginPayload(BaseModel):
    email: str
    password: str


class UserActionPayload(BaseModel):
    action: Literal[
        "ban",
        "unban",
        "add_balance",
        "sub_balance",
        "add_traffic",
        "sub_traffic",
        "extend_subscription",
        "reduce_subscription",
    ]
    amount: int | None = None
    gb: float | None = Field(default=None, gt=0)
    duration_hours: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=512)


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
    reduce_days: int | None = Field(default=None, gt=0)
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
    "re",
    "uuid",
    "datetime",
    "timedelta",
    "timezone",
    "Path",
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
    "require_admin_auth",
    "require_superadmin_auth",
    "require_support_auth",
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
