from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.bot.common import (
    ConfirmPaymentPayload,
    PaymentPayload,
    TransactionNotFound,
    UserNotFound,
    _apply_referral_reward,
    _get_user_or_404,
    _map_service_error,
    get_user_service,
    require_bot_auth,
)
from backend.core.business_config import get_business_int
from backend.services.payment_method_service import get_payment_method_config, is_payment_method_enabled
from backend.services import BillingService, TransactionService
from backend.services.email_notification_service import EmailNotificationService

router = APIRouter(dependencies=[Depends(require_bot_auth)])


@router.post("/users/by-tg/{tg_id}/payments/platega")
async def create_platega_payment(tg_id: int, payload: PaymentPayload, user_service=Depends(get_user_service)):
    if not await is_payment_method_enabled(user_service.session, "platega"):
        raise HTTPException(status_code=503, detail="Platega временно отключён")
    user = await _get_user_or_404(user_service, tg_id)
    billing = BillingService(user_service.session)
    try:
        config = await get_payment_method_config(user_service.session, "platega")
        requested_method = int(payload.payment_method or 2)
        card_method = int(config.get("method_card", 11))
        sbp_method = int(config.get("method_sbp", 2))
        # Older bot clients send 11/2; map those values to the current
        # admin-managed provider method IDs.
        payment_method = card_method if requested_method in (11, card_method) else sbp_method
        payment = await billing.create_platega_payment(user_id=user.id, amount=payload.amount, payment_method=payment_method, description=payload.description, return_url=payload.return_url, failed_url=payload.failed_url)
    except Exception as e:
        raise _map_service_error(e)
    finally:
        await billing.close_clients()
    return {"ok": True, "payment": payment}


@router.post("/users/by-tg/{tg_id}/payments/platega/confirm")
async def confirm_platega_payment(tg_id: int, payload: ConfirmPaymentPayload, user_service=Depends(get_user_service)):
    if not payload.provider_transaction_id:
        raise HTTPException(status_code=400, detail="provider_transaction_id is required")
    billing = BillingService(user_service.session)
    tx_service = TransactionService(user_service.session)
    try:
        existing = await tx_service.get_by_provider_id(payload.provider_transaction_id)
    except TransactionNotFound:
        raise HTTPException(status_code=404, detail="transaction not found")
    paid_before = bool(getattr(existing, "paid", False))
    try:
        tx = await billing.confirm_platega_payment(payload.provider_transaction_id)
    except Exception as e:
        raise _map_service_error(e)
    finally:
        await billing.close_clients()
    reward = {"bonus": 0, "referrer_tg_id": None}
    if not paid_before:
        reward = await _apply_referral_reward(session=user_service.session, transaction_user_id=tx.user_id, amount=int(tx.amount or 0))
    try:
        fresh_user = await user_service.get_by_id(tx.user_id)
    except UserNotFound:
        fresh_user = None
    if fresh_user:
        await EmailNotificationService(user_service.session).payment_confirmed(user=fresh_user, transaction=tx)
    return {"ok": True, "confirmed": True, "transaction": {"id": tx.id, "provider_id": tx.transaction_id, "amount": int(tx.amount or 0)}, "balance": int(fresh_user.balance or 0) if fresh_user else 0, "referral_bonus": int(reward["bonus"] or 0), "referrer_tg_id": reward["referrer_tg_id"]}


@router.post("/users/by-tg/{tg_id}/payments/crypto")
async def create_crypto_invoice(tg_id: int, payload: PaymentPayload, user_service=Depends(get_user_service)):
    if not await is_payment_method_enabled(user_service.session, "cryptobot"):
        raise HTTPException(status_code=503, detail="CryptoBot временно отключён")
    user = await _get_user_or_404(user_service, tg_id)
    billing = BillingService(user_service.session)
    try:
        invoice = await billing.create_crypto_invoice(user_id=user.id, amount_rub=int(payload.amount), asset=payload.asset or "USDT", description=payload.description, expires_in=payload.expires_in or get_business_int("CRYPTO_INVOICE_EXPIRES_IN_SEC"))
    except Exception as e:
        raise _map_service_error(e)
    finally:
        await billing.close_clients()
    return {"ok": True, "invoice": invoice}


@router.post("/users/by-tg/{tg_id}/payments/crypto/confirm")
async def confirm_crypto_invoice(tg_id: int, payload: ConfirmPaymentPayload, user_service=Depends(get_user_service)):
    if payload.invoice_id is None:
        raise HTTPException(status_code=400, detail="invoice_id is required")
    billing = BillingService(user_service.session)
    tx_service = TransactionService(user_service.session)
    try:
        existing = await tx_service.get_by_provider_id(str(payload.invoice_id))
    except TransactionNotFound:
        raise HTTPException(status_code=404, detail="transaction not found")
    paid_before = bool(getattr(existing, "paid", False))
    try:
        tx = await billing.confirm_crypto_payment(payload.invoice_id)
    except Exception as e:
        raise _map_service_error(e)
    finally:
        await billing.close_clients()
    reward = {"bonus": 0, "referrer_tg_id": None}
    if not paid_before:
        reward = await _apply_referral_reward(session=user_service.session, transaction_user_id=tx.user_id, amount=int(tx.amount or 0))
    try:
        fresh_user = await user_service.get_by_id(tx.user_id)
    except UserNotFound:
        fresh_user = None
    if fresh_user:
        await EmailNotificationService(user_service.session).payment_confirmed(user=fresh_user, transaction=tx)
    return {"ok": True, "confirmed": True, "transaction": {"id": tx.id, "provider_id": tx.transaction_id, "amount": int(tx.amount or 0)}, "balance": int(fresh_user.balance or 0) if fresh_user else 0, "referral_bonus": int(reward["bonus"] or 0), "referrer_tg_id": reward["referrer_tg_id"]}


@router.post("/users/by-tg/{tg_id}/payments/pally")
async def create_pally_payment(tg_id: int, payload: PaymentPayload, user_service=Depends(get_user_service)):
    if not await is_payment_method_enabled(user_service.session, "pally"):
        raise HTTPException(status_code=503, detail="Pally временно отключён")
    user = await _get_user_or_404(user_service, tg_id)
    billing = BillingService(user_service.session)
    try:
        payment = await billing.create_pally_payment(user_id=user.id, amount=payload.amount, description=payload.description, return_url=payload.return_url, failed_url=payload.failed_url, ttl=payload.ttl or get_business_int("PALLY_INVOICE_TTL_SEC"))
    except Exception as e:
        raise _map_service_error(e)
    finally:
        await billing.close_clients()
    return {"ok": True, "payment": payment}


@router.post("/users/by-tg/{tg_id}/payments/pally/confirm")
async def confirm_pally_payment(tg_id: int, payload: ConfirmPaymentPayload, user_service=Depends(get_user_service)):
    if not payload.provider_transaction_id:
        raise HTTPException(status_code=400, detail="provider_transaction_id is required")
    billing = BillingService(user_service.session)
    tx_service = TransactionService(user_service.session)
    try:
        existing = await tx_service.get_by_provider_id(payload.provider_transaction_id)
    except TransactionNotFound:
        raise HTTPException(status_code=404, detail="transaction not found")
    paid_before = bool(getattr(existing, "paid", False))
    try:
        tx = await billing.confirm_pally_payment(payload.provider_transaction_id)
    except Exception as e:
        raise _map_service_error(e)
    finally:
        await billing.close_clients()
    reward = {"bonus": 0, "referrer_tg_id": None}
    if not paid_before:
        reward = await _apply_referral_reward(session=user_service.session, transaction_user_id=tx.user_id, amount=int(tx.amount or 0))
    try:
        fresh_user = await user_service.get_by_id(tx.user_id)
    except UserNotFound:
        fresh_user = None
    if fresh_user:
        await EmailNotificationService(user_service.session).payment_confirmed(user=fresh_user, transaction=tx)
    return {"ok": True, "confirmed": True, "transaction": {"id": tx.id, "provider_id": tx.transaction_id, "amount": int(tx.amount or 0)}, "balance": int(fresh_user.balance or 0) if fresh_user else 0, "referral_bonus": int(reward["bonus"] or 0), "referrer_tg_id": reward["referrer_tg_id"]}
