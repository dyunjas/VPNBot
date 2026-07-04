from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.bot.common import (
    MIN_WITHDRAW_AMOUNT,
    WithdrawalPayload,
    _get_user_or_404,
    _map_service_error,
    get_user_service,
    require_bot_auth,
)
from backend.services import ReferralService, TransactionService, WithdrawalService

router = APIRouter(dependencies=[Depends(require_bot_auth)])


@router.get("/users/by-tg/{tg_id}/profile")
async def profile(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    referral_service = ReferralService(user_service.session)
    transaction_service = TransactionService(user_service.session)
    account = await referral_service.get_account(user.id) or await referral_service.create_account(user.id)
    txs = await transaction_service.list_by_user(user.id)
    return {"ok": True, "user": {"id": user.id, "tg_id": user.tg_id, "username": user.username, "email": user.email, "balance": int(user.balance or 0)}, "referral": {"balance": int(account.referral_balance or 0), "percent": int(account.referral_percent or 0), "invited_count": int(account.invited_count or 0)}, "transactions": [{"id": tx.id, "amount": int(tx.amount or 0), "payment_system": tx.payment_system, "transaction_id": tx.transaction_id, "paid": bool(tx.paid), "created_at": tx.created_at.isoformat() if tx.created_at else None, "paid_at": tx.paid_at.isoformat() if tx.paid_at else None} for tx in txs[:50]]}


@router.get("/users/by-tg/{tg_id}/transactions")
async def transactions(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    txs = await TransactionService(user_service.session).list_by_user(user.id)
    return {"ok": True, "items": [{"id": tx.id, "amount": int(tx.amount or 0), "payment_system": tx.payment_system, "transaction_id": tx.transaction_id, "paid": bool(tx.paid), "created_at": tx.created_at.isoformat() if tx.created_at else None, "paid_at": tx.paid_at.isoformat() if tx.paid_at else None} for tx in txs]}


@router.get("/users/by-tg/{tg_id}/transactions/{transaction_id}")
async def transaction_detail(tg_id: int, transaction_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    tx = await TransactionService(user_service.session).get_by_id_for_user(transaction_id, user.id)
    return {"ok": True, "transaction": {"id": tx.id, "amount": int(tx.amount or 0), "payment_system": tx.payment_system, "transaction_id": tx.transaction_id, "paid": bool(tx.paid), "created_at": tx.created_at.isoformat() if tx.created_at else None, "paid_at": tx.paid_at.isoformat() if tx.paid_at else None}}


@router.get("/users/by-tg/{tg_id}/referral")
async def referral_info(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    account = await ReferralService(user_service.session).get_account(user.id) or await ReferralService(user_service.session).create_account(user.id)
    return {"ok": True, "referral": {"balance": int(account.referral_balance or 0), "percent": int(account.referral_percent or 0), "invited_count": int(account.invited_count or 0)}}


@router.post("/users/by-tg/{tg_id}/withdrawals")
async def create_withdrawal(tg_id: int, payload: WithdrawalPayload, user_service=Depends(get_user_service)):
    if payload.amount < MIN_WITHDRAW_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Минимальная сумма вывода: {MIN_WITHDRAW_AMOUNT} RUB")
    user = await _get_user_or_404(user_service, tg_id)
    try:
        wd = await WithdrawalService(user_service.session).create_withdrawal(user_id=user.id, amount=payload.amount, method=payload.method)
    except Exception as e:
        raise _map_service_error(e)
    return {"ok": True, "withdrawal": {"id": wd.id, "amount": int(wd.amount), "method": wd.method, "status": wd.status.value if wd.status else None, "created_at": wd.created_at.isoformat() if wd.created_at else None}}


@router.get("/users/by-tg/{tg_id}/withdrawals")
async def list_withdrawals(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    rows = await WithdrawalService(user_service.session).list_by_user(user_id=user.id, limit=20)
    return {"ok": True, "items": [{"id": w.id, "amount": int(w.amount), "method": w.method, "status": w.status.value if w.status else None, "created_at": w.created_at.isoformat() if w.created_at else None} for w in rows]}
