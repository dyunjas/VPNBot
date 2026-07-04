from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.cabinet.common import (
    ApplyPromocodePayload,
    CreateWithdrawalPayload,
    InitPayload,
    PromoService,
    ReferralService,
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
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        service = ReferralService(session)
        account = await service.get_account(user.id) or await service.create_account(user.id)
        await session.commit()
        referral_url = f"https://t.me/{getattr(settings, 'BOT_USERNAME', 'LunetVPNBot')}?start=ref_{user.tg_id}"
        return {"ok": True, "referral_url": referral_url, "referral": {"invited_count": int(account.invited_count or 0), "balance": int(account.referral_balance or 0), "percent": int(account.referral_percent or 0)}}


@router.post("/referral/withdrawals")
async def cabinet_referral_withdrawals(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        rows = await WithdrawalService(session).list_by_user(user_id=user.id, limit=20)
        return {"ok": True, "items": [{"id": w.id, "amount": int(w.amount), "method": w.method, "status": w.status.value if w.status else None, "created_at": w.created_at.isoformat() if w.created_at else None} for w in rows]}


@router.post("/referral/withdraw")
async def cabinet_referral_withdraw(payload: CreateWithdrawalPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
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
async def cabinet_promocode_apply(payload: ApplyPromocodePayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
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
