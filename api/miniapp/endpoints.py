from __future__ import annotations

from typing import Any, Optional

from aiogram.utils.web_app import safe_parse_webapp_init_data
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.loader import settings
from backend.database.session import async_session
from backend.database.models import KeyStatus

from backend.services import (
    BillingService,
    PromoService,
    SubscriptionService,
    TransactionService,
    UserService,
    VPNService,
)
from backend.services.exceptions import (
    UserNotFound,
    SubscriptionNotFound,
    PlanNotFound,
    InsufficientBalance,
    TransactionNotFound,
    PaymentNotConfirmed,
    PromocodeNotFound,
    PromocodeAlreadyUsed,
    PromocodeExhausted,
    KeyCreationError,
    ServerNotFound,
)

router = APIRouter(prefix="/mini", tags=["mini-app"])

BOT_TOKEN = settings.BOT_TOKEN
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in settings")

XRAY_AUTH_TOKEN = settings.XRAY_AUTH
if not XRAY_AUTH_TOKEN:
    raise RuntimeError("XRAY_AUTH is not set in settings")

# ✅ Platega payment_method mapping (проверь коды у твоего провайдера)
PLATEGA_METHOD_CARD = 11
PLATEGA_METHOD_SBP = 2  # <-- если у тебя другой код СБП — поменяй

# ✅ Bot username / setup link
BOT_USERNAME = getattr(settings, "BOT_USERNAME", "LunetVPNBot")
SETUP_URL_FALLBACK = getattr(settings, "SETUP_URL", "https://t.me/LunetVPNBot")


class InitPayload(BaseModel):
    initData: Optional[str] = None


class CreateKeyPayload(InitPayload):
    server_id: int
    label: str | None = None


class DeleteKeyPayload(InitPayload):
    key_id: int


class BuySubscriptionPayload(InitPayload):
    plan_id: int


class TopupPayload(InitPayload):
    amount: int
    method: str = "platega"   # "platega" | "crypto"
    asset: str = "USDT"       # crypto only (можешь оставить)
    platega_type: str = "card"  # "card" | "sbp"


class BalanceCheckPayload(InitPayload):
    method: str = "platega"
    provider_id: str | None = None


class ApplyPromocodePayload(InitPayload):
    code: str


def _get_tg_user(init_data: Optional[str]) -> dict[str, Any]:
    if not init_data:
        raise HTTPException(401, "initData is missing. Откройте мини-приложение из Telegram.")

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
    if isinstance(e, InsufficientBalance):
        return HTTPException(status_code=402, detail="Not enough balance")
    if isinstance(e, PaymentNotConfirmed):
        return HTTPException(status_code=409, detail=str(e) or "Payment not confirmed")

    if isinstance(e, PlanNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Plan not found")
    if isinstance(e, SubscriptionNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Subscription not found")

    if isinstance(e, UserNotFound):
        return HTTPException(status_code=404, detail=str(e) or "User not found")
    if isinstance(e, TransactionNotFound):
        return HTTPException(status_code=404, detail=str(e) or "Transaction not found")

    if isinstance(e, PromocodeNotFound):
        return HTTPException(status_code=404, detail="promocode not found")
    if isinstance(e, PromocodeAlreadyUsed):
        return HTTPException(status_code=409, detail="promocode already used by this user")
    if isinstance(e, PromocodeExhausted):
        return HTTPException(status_code=409, detail="promocode usage limit reached")

    if isinstance(e, ServerNotFound):
        return HTTPException(status_code=404, detail="server not found")
    if isinstance(e, KeyCreationError):
        return HTTPException(status_code=500, detail=str(e) or "key creation error")

    return HTTPException(status_code=500, detail=str(e) or "internal error")


@router.post("/referral")
async def mini_referral(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        # ✅ базовая реф-ссылка
        referral_url = f"https://t.me/{BOT_USERNAME}?start=ref_{user.tg_id}"

        return {
            "ok": True,
            "referral_url": referral_url,
            "hint": "Скопируйте ссылку и отправьте другу. Бонусы начисляются после регистрации друга.",
        }


@router.post("/setup")
async def mini_setup(payload: InitPayload):
    _ = _get_tg_user(payload.initData)
    return {"ok": True, "setup_url": SETUP_URL_FALLBACK}


@router.post("/status")
async def mini_status(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        sub_service = SubscriptionService(session)
        vpn_service = VPNService(session, xray_auth_token=XRAY_AUTH_TOKEN)

        subscription = await sub_service.get_active_subscription(user.id)
        active_keys = await vpn_service.list_active_keys(user.id)

        sub_token = user.subscription_token
        sub_url = f"https://lunetpn.ru/sub/{sub_token}" if sub_token else None

        if not subscription:
            return {
                "ok": False,
                "has_subscription": False,
                "statusText": f"Нет активной подписки. Активных ключей: {len(active_keys)}",
                "active_keys": len(active_keys),
                "subscription_token": sub_token,
                "subscription_url": sub_url,
            }

        plan = subscription.plan
        status_text = (
            f"Тариф: {plan.name} • Ключей: {len(active_keys)}/{getattr(plan, 'key_limit', '—')}\n"
            f"Подписка до: {subscription.current_period_end.strftime('%d.%m.%Y %H:%M')}"
        )

        return {
            "ok": True,
            "has_subscription": True,
            "statusText": status_text,
            "active_keys": len(active_keys),
            "subscription_token": sub_token,
            "subscription_url": sub_url,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "key_limit": getattr(plan, "key_limit", None),
                "price": plan.price,
                "period_days": plan.period_days,
                "gb_limit": str(getattr(plan, "gb_limit", None))
                if getattr(plan, "gb_limit", None) is not None
                else None,
            },
            "subscription": {
                "current_period_start": subscription.current_period_start.isoformat()
                if subscription.current_period_start
                else None,
                "current_period_end": subscription.current_period_end.isoformat()
                if subscription.current_period_end
                else None,
                "status": subscription.status.value if subscription.status else None,
                "gb_left": str(subscription.gb_left) if subscription.gb_left is not None else None,
            },
        }


@router.post("/plans")
async def mini_plans(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        _ = await _get_user_or_404(session, tg_id)

        sub_service = SubscriptionService(session)
        plans = await sub_service.list_plans()

        return {
            "ok": True,
            "plans": [
                {
                    "id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "period_days": p.period_days,
                    "key_limit": getattr(p, "key_limit", None),
                    "gb_limit": str(getattr(p, "gb_limit", None))
                    if getattr(p, "gb_limit", None) is not None
                    else None,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in plans
            ],
        }


@router.post("/subscription/buy")
async def mini_subscription_buy(payload: BuySubscriptionPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        billing = BillingService(session)

        try:
            sub = await billing.buy_subscription(user_id=user.id, plan_id=payload.plan_id, auto_renew=True)
        except Exception as e:
            raise _map_service_error(e)

        sub_service = SubscriptionService(session)
        plan = await sub_service.get_plan(sub.plan_id)

        return {
            "ok": True,
            "subscription": {
                "id": sub.id,
                "plan_id": plan.id,
                "plan_name": plan.name,
                "current_period_start": sub.current_period_start.isoformat(),
                "current_period_end": sub.current_period_end.isoformat(),
                "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status),
            },
        }


@router.post("/profile")
async def mini_profile(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        tx_service = TransactionService(session)
        txs = await tx_service.list_by_user(user.id)
        txs = txs[:50]

        return {
            "ok": True,
            "user": {
                "tg_id": user.tg_id,
                "username": user.username,
                "balance": user.balance,
                "email": user.email,
                "subscription_token": user.subscription_token,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
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


@router.post("/promocode/apply")
async def mini_promocode_apply(payload: ApplyPromocodePayload):
    code = (payload.code or "").strip()
    if not code:
        raise HTTPException(400, "code is required")

    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        promo_service = PromoService(session)
        try:
            promo = await promo_service.activate_promocode(user_id=user.id, code=code)
        except Exception as e:
            raise _map_service_error(e)

        user_service = UserService(session)
        fresh_user = await user_service.get_by_id(user.id)

        return {
            "ok": True,
            "amount_added": int(promo.amount or 0),
            "balance": fresh_user.balance,
        }


@router.post("/balance/topup")
async def mini_balance_topup(payload: TopupPayload):
    if payload.amount <= 0:
        raise HTTPException(400, "amount must be positive")

    method = (payload.method or "platega").lower().strip()
    if method not in ("platega", "crypto"):
        raise HTTPException(400, "method must be 'platega' or 'crypto'")

    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        billing = BillingService(session)

        try:
            if method == "platega":
                amount = float(payload.amount)
                pl_type = (payload.platega_type or "card").lower().strip()
                if pl_type not in ("card", "sbp"):
                    raise HTTPException(400, "platega_type must be 'card' or 'sbp'")

                payment_method = PLATEGA_METHOD_CARD if pl_type == "card" else PLATEGA_METHOD_SBP

                payment = await billing.create_platega_payment(
                    user_id=user.id,
                    amount=amount,
                    payment_method=payment_method,
                    description=f"Пополнение баланса на {amount} RUB",
                    return_url="https://t.me/LunetVPNBot",
                    failed_url="https://t.me/LunetVPNBot",
                )

                payment_url = (
                    payment.get("redirect")
                    or payment.get("payformSuccessUrl")
                    or payment.get("payment_url")
                )
                provider_id = str(payment.get("id") or payment.get("transactionId") or "")

                return {
                    "ok": True,
                    "method": "platega",
                    "platega_type": pl_type,
                    "payment_url": payment_url,
                    "provider_id": provider_id,
                    "status": payment.get("status"),
                }

            # crypto
            invoice = await billing.create_crypto_invoice(
                user_id=user.id,
                amount_rub=int(payload.amount),
                asset=(payload.asset or "USDT"),
                description=f"Пополнение баланса на {payload.amount} RUB (CryptoBot)",
                expires_in=900,
            )

            payment_url = (
                invoice.get("pay_url")
                or invoice.get("bot_invoice_url")
                or invoice.get("mini_app_invoice_url")
                or invoice.get("web_app_invoice_url")
                or invoice.get("url")
            )
            invoice_id = invoice.get("invoice_id")

            return {
                "ok": True,
                "method": "crypto",
                "payment_url": payment_url,
                "provider_id": str(invoice_id) if invoice_id is not None else None,
                "status": invoice.get("status"),
                "asset": payload.asset or "USDT",
            }

        except HTTPException:
            raise
        except Exception as e:
            raise _map_service_error(e)


@router.post("/balance/check")
async def mini_balance_check(payload: BalanceCheckPayload):
    method = (payload.method or "platega").lower().strip()
    if method not in ("platega", "crypto"):
        raise HTTPException(400, "method must be 'platega' or 'crypto'")

    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        billing = BillingService(session)
        tx_service = TransactionService(session)
        user_service = UserService(session)

        provider_id = (payload.provider_id or "").strip() or None

        if not provider_id:
            payment_system = "Platega" if method == "platega" else "CRYPTOBOT"
            tx = await tx_service.get_last_unpaid_by_system(user_id=user.id, payment_system=payment_system)
            if not tx:
                return {"ok": False, "reason": "no_pending", "message": "Нет незавершённых платежей"}
            provider_id = tx.transaction_id

        try:
            if method == "platega":
                await billing.confirm_platega_payment(provider_id)
            else:
                try:
                    invoice_id = int(provider_id)
                except ValueError:
                    raise HTTPException(400, "provider_id must be invoice_id (int) for crypto")
                await billing.confirm_crypto_payment(invoice_id)

        except PaymentNotConfirmed:
            try:
                tx = await tx_service.get_by_provider_id(provider_id)
            except TransactionNotFound:
                return {"ok": False, "reason": "tx_not_found", "message": "Transaction not found"}

            fresh_user = await user_service.get_by_id(user.id)
            return {
                "ok": True,
                "confirmed": False,
                "method": method,
                "transaction": {
                    "id": tx.id,
                    "provider_id": tx.transaction_id,
                    "amount": int(tx.amount) if tx.amount is not None else None,
                    "paid": tx.paid,
                    "status_raw": "NOT_CONFIRMED",
                },
                "balance": fresh_user.balance,
            }
        except Exception as e:
            raise _map_service_error(e)

        tx = await tx_service.get_by_provider_id(provider_id)
        fresh_user = await user_service.get_by_id(user.id)

        return {
            "ok": True,
            "confirmed": True,
            "method": method,
            "transaction": {
                "id": tx.id,
                "provider_id": tx.transaction_id,
                "amount": int(tx.amount) if tx.amount is not None else None,
                "paid": True,
                "status_raw": "CONFIRMED",
            },
            "balance": fresh_user.balance,
        }
