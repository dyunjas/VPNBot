from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.database.session import async_session
from backend.services import (
    BillingService,
    PartnerService,
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

TRIAL_PLAN_ID = 9
MIN_WITHDRAW_AMOUNT = 500


def _bot_token() -> str:
    token = (settings.BOT_API_TOKEN or settings.SECRET_KEY or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="BOT_API_TOKEN is not configured")
    return token


async def require_bot_auth(
    x_bot_token: str | None = Header(default=None, alias="X-Bot-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    token = (x_bot_token or "").strip()
    if not token and authorization:
        raw = authorization.strip()
        token = raw[7:].strip() if raw.lower().startswith("bearer ") else raw
    if not token or token != _bot_token():
        raise HTTPException(status_code=401, detail="Unauthorized")


class TgUserPayload(BaseModel):
    tg_id: int
    username: str | None = None


class UsernamePayload(BaseModel):
    username: str | None = None


class EmailPayload(BaseModel):
    email: str | None = None


class ReferrerPayload(BaseModel):
    referrer_tg_id: int


class PartnerPayload(BaseModel):
    code: str


class TrialPayload(BaseModel):
    auto_renew: bool = False


class PlanBuyPayload(BaseModel):
    plan_id: int
    auto_renew: bool = True


class TrafficBuyPayload(BaseModel):
    gb: int


class AutoRenewPayload(BaseModel):
    auto_renew: bool


class WithdrawalPayload(BaseModel):
    amount: int
    method: str


class PromocodePayload(BaseModel):
    code: str


class PaymentPayload(BaseModel):
    amount: float
    payment_method: int | None = None
    description: str | None = None
    return_url: str | None = None
    failed_url: str | None = None
    asset: str | None = None
    expires_in: int | None = None
    ttl: int | None = None


class ConfirmPaymentPayload(BaseModel):
    provider_transaction_id: str | None = None
    invoice_id: int | None = None


def _map_service_error(e: Exception) -> HTTPException:
    if isinstance(e, InsufficientBalance):
        return HTTPException(status_code=402, detail="Недостаточно средств на балансе")
    if isinstance(e, NotEnoughReferralBalance):
        return HTTPException(status_code=402, detail="Недостаточно реферального баланса")
    if isinstance(e, PaymentNotConfirmed):
        return HTTPException(status_code=409, detail="Transaction not approved")
    if isinstance(e, PurchaseInProgress):
        return HTTPException(status_code=409, detail="Покупка уже обрабатывается")
    if isinstance(e, BannedUser):
        return HTTPException(status_code=403, detail="banned")
    if isinstance(e, PlanNotFound):
        return HTTPException(status_code=404, detail="plan not found")
    if isinstance(e, SubscriptionNotFound):
        return HTTPException(status_code=404, detail="subscription not found")
    if isinstance(e, TooEarlyToRenew):
        return HTTPException(status_code=409, detail="too early to renew")
    if isinstance(e, TransactionNotFound):
        return HTTPException(status_code=404, detail="transaction not found")
    if isinstance(e, UserNotFound):
        return HTTPException(status_code=404, detail="user not found")
    if isinstance(e, PromocodeNotFound):
        return HTTPException(status_code=404, detail="promocode not found")
    if isinstance(e, PromocodeAlreadyUsed):
        return HTTPException(status_code=409, detail="promocode already used")
    if isinstance(e, PromocodeExhausted):
        return HTTPException(status_code=409, detail="promocode exhausted")
    return HTTPException(status_code=500, detail=str(e) or "internal error")


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


async def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


async def get_referral_service(session: AsyncSession = Depends(get_session)) -> ReferralService:
    return ReferralService(session)


async def get_subscription_service(session: AsyncSession = Depends(get_session)) -> SubscriptionService:
    return SubscriptionService(session)


async def get_transaction_service(session: AsyncSession = Depends(get_session)) -> TransactionService:
    return TransactionService(session)


async def get_billing_service(session: AsyncSession = Depends(get_session)):
    billing = BillingService(session)
    try:
        yield billing
    finally:
        await billing.close_clients()


async def get_remnawave_service(session: AsyncSession = Depends(get_session)) -> RemnaWaveService:
    return RemnaWaveService(session)


async def get_partner_service(session: AsyncSession = Depends(get_session)) -> PartnerService:
    return PartnerService(session)


async def get_promo_service(session: AsyncSession = Depends(get_session)) -> PromoService:
    return PromoService(session)


async def get_withdrawal_service(session: AsyncSession = Depends(get_session)) -> WithdrawalService:
    return WithdrawalService(session)


async def _get_user_or_404(user_service: UserService, tg_id: int):
    try:
        return await user_service.get_by_tg_id(tg_id)
    except UserNotFound as exc:
        raise HTTPException(status_code=404, detail="user not found") from exc


async def _apply_referral_reward(*, session: AsyncSession, transaction_user_id: int, amount: int) -> dict[str, Any]:
    referral_service = ReferralService(session)
    user_service = UserService(session)
    try:
        payer = await user_service.get_by_id(transaction_user_id)
    except UserNotFound:
        return {"bonus": 0, "referrer_tg_id": None}
    bonus = await referral_service.reward_from_purchase(user_id=payer.id, purchase_amount=amount)
    referrer_tg_id = None
    if bonus > 0 and getattr(payer, "referrer_id", None):
        try:
            referrer = await user_service.get_by_id(int(payer.referrer_id))
            referrer_tg_id = referrer.tg_id
        except Exception:
            referrer_tg_id = None
    return {"bonus": bonus, "referrer_tg_id": referrer_tg_id}
