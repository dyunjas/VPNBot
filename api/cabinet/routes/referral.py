from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.core.business_config import get_business_int, list_business_settings
from api.cabinet.common import (
    ApplyPromocodePayload,
    CreateWithdrawalPayload,
    InitPayload,
    PromoService,
    ReferralService,
    ReferralTransferPayload,
    UserService,
    WithdrawalService,
    _get_user,
    _map_service_error,
    _resolve_request_user_id,
    async_session,
    require_optional_cabinet_auth,
    settings,
)

router = APIRouter()


@router.post("/referral/info")
async def cabinet_referral_info(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        service = ReferralService(session)
        account = await service.get_account(user.id) or await service.create_account(user.id)
        await session.commit()
        referral_url = (
            f"https://t.me/{getattr(settings, 'BOT_USERNAME', 'LunetVPNBot')}?start=ref_{user.tg_id}"
            if user.tg_id
            else None
        )
        return {
            "ok": True,
            "referral_url": referral_url,
            "referral": {
                "invited_count": int(account.invited_count or 0),
                "balance": int(account.referral_balance or 0),
                "percent": int(account.referral_percent or 0),
            },
            "business_settings": {item["key"]: item["value"] for item in list_business_settings()},
        }


@router.post("/referral/withdrawals")
async def cabinet_referral_withdrawals(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        rows = await WithdrawalService(session).list_by_user(user_id=user.id, limit=20)
        return {
            "ok": True,
            "items": [
                {
                    "id": w.id,
                    "amount": int(w.amount),
                    "method": w.method,
                    "status": w.status.value if w.status else None,
                    "created_at": w.created_at.isoformat() if w.created_at else None,
                }
                for w in rows
            ],
        }


@router.post("/referral/withdraw")
async def cabinet_referral_withdraw(payload: CreateWithdrawalPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    amount = int(payload.amount or 0)
    method = (payload.method or "").strip()
    min_amount = get_business_int("MIN_WITHDRAW_AMOUNT_RUB")
    if amount < min_amount:
        raise HTTPException(400, f"Минимальная сумма вывода: {min_amount} RUB")
    if len(method) < 8:
        raise HTTPException(400, "Укажите способ вывода и реквизиты получателя")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        try:
            wd = await WithdrawalService(session).create_withdrawal(user_id=user.id, amount=amount, method=method)
        except Exception as e:
            raise _map_service_error(e)
        return {
            "ok": True,
            "withdrawal": {
                "id": wd.id,
                "amount": int(wd.amount),
                "method": wd.method,
                "status": wd.status.value if wd.status else None,
                "created_at": wd.created_at.isoformat() if wd.created_at else None,
            },
            "message": "Заявка на вывод создана и передана на обработку",
        }


@router.post("/referral/transfer")
async def cabinet_referral_transfer(payload: ReferralTransferPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    amount = int(payload.amount or 0)
    min_amount = get_business_int("MIN_REFERRAL_TRANSFER_AMOUNT_RUB")
    if amount < min_amount:
        raise HTTPException(400, f"Минимальная сумма перевода: {min_amount} RUB")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        try:
            result = await ReferralService(session).transfer_to_user_balance(user_id=user.id, amount=amount)
        except Exception as e:
            raise _map_service_error(e)
        return {"ok": True, **result}


@router.post("/promocode/apply")
async def cabinet_promocode_apply(payload: ApplyPromocodePayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    code = (payload.code or "").strip()
    if not code:
        raise HTTPException(400, "Введите промокод")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        promo_service = PromoService(session)
        try:
            promo = await promo_service.activate_promocode(user_id=user.id, code=code)
        except Exception as e:
            raise _map_service_error(e)
        fresh_user = await UserService(session).get_by_id(user.id)
        return {"ok": True, "amount_added": int(promo.amount or 0), "balance": fresh_user.balance}
