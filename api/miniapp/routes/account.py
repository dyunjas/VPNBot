from fastapi import APIRouter

from ..common import *
from backend.core.business_config import get_business_int, list_business_settings

router = APIRouter()

@router.post("/devices")
async def mini_devices(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        remnawave_service = RemnaWaveService(session)
        devices = await remnawave_service.get_user_hwid_devices(user=user)

        return {
            "ok": True,
            "items": [
                {
                    "id": i,
                    "hwid": d.get("hwid"),
                    "device_model": d.get("deviceModel"),
                    "device_os": d.get("platform"),
                    "os_version": d.get("osVersion"),
                    "device_locale": None,
                    "user_agent": d.get("userAgent"),
                    "first_seen_at": d.get("createdAt"),
                    "last_seen_at": d.get("updatedAt"),
                }
                for i, d in enumerate(devices)
            ],
        }


@router.post("/device/delete")
async def mini_device_delete(payload: DeleteDevicePayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        remnawave_service = RemnaWaveService(session)

        try:
            devices = await remnawave_service.get_user_hwid_devices(user=user)
            if payload.device_id < 0 or payload.device_id >= len(devices):
                raise HTTPException(status_code=404, detail="device not found")
            hwid = str(devices[payload.device_id].get("hwid") or "").strip()
            if not hwid:
                raise HTTPException(status_code=404, detail="device not found")
            ok = await remnawave_service.delete_hwid_device(user=user, hwid=hwid)
            if not ok:
                raise HTTPException(status_code=502, detail="remnawave delete device failed")
        except HTTPException:
            raise
        except Exception as e:
            raise _map_service_error(e)

        return {"ok": True, "deleted_device_id": payload.device_id}


@router.post("/referral/info")
async def mini_referral_info(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        referral_service = ReferralService(session)

        account = await referral_service.get_account(user.id)
        if not account:
            account = await referral_service.create_account(user.id)
            await session.commit()
        referral_url = f"https://t.me/{BOT_USERNAME}?start=ref_{user.tg_id}"

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


@router.post("/referral/withdraw")
async def mini_referral_withdraw(payload: CreateWithdrawalPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    amount = int(payload.amount or 0)
    method = (payload.method or "").strip()

    min_amount = get_business_int("MIN_WITHDRAW_AMOUNT_RUB")
    if amount < min_amount:
        raise HTTPException(400, f"Минимальная сумма вывода: {min_amount} RUB")
    if len(method) < 8:
        raise HTTPException(400, "Укажите способ вывода и реквизиты получателя")

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        withdrawal_service = WithdrawalService(session)

        try:
            wd = await withdrawal_service.create_withdrawal(
                user_id=user.id,
                amount=amount,
                method=method,
            )
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
async def mini_referral_transfer(payload: ReferralTransferPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]
    amount = int(payload.amount or 0)

    min_amount = get_business_int("MIN_REFERRAL_TRANSFER_AMOUNT_RUB")
    if amount < min_amount:
        raise HTTPException(400, f"Минимальная сумма перевода: {min_amount} RUB")

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        try:
            result = await ReferralService(session).transfer_to_user_balance(
                user_id=user.id,
                amount=amount,
            )
        except Exception as e:
            raise _map_service_error(e)

        return {"ok": True, **result}


@router.post("/referral/withdrawals")
async def mini_referral_withdrawals(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        withdrawal_service = WithdrawalService(session)

        rows = await withdrawal_service.list_by_user(user_id=user.id, limit=20)

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

