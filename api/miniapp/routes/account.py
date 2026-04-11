from fastapi import APIRouter

from ..common import *

router = APIRouter()

MIN_WITHDRAW_AMOUNT = 500


@router.post("/devices")
async def mini_devices(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        device_service = DeviceService(session)

        devices = await device_service.list_devices(user.id)

        return {
            "ok": True,
            "items": [
                {
                    "id": d.id,
                    "hwid": d.hwid,
                    "device_model": d.device_model,
                    "device_os": d.device_os,
                    "os_version": d.os_version,
                    "device_locale": d.device_locale,
                    "user_agent": d.user_agent,
                    "first_seen_at": d.first_seen_at.isoformat() if d.first_seen_at else None,
                    "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                }
                for d in devices
            ],
        }


@router.post("/device/delete")
async def mini_device_delete(payload: DeleteDevicePayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        device_service = DeviceService(session)

        try:
            await device_service.remove_device_for_user(user_id=user.id, device_id=payload.device_id)
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

        account = await referral_service.create_account(user.id)
        referral_url = f"https://t.me/{BOT_USERNAME}?start=ref_{user.tg_id}"

        return {
            "ok": True,
            "referral_url": referral_url,
            "referral": {
                "invited_count": int(account.invited_count or 0),
                "balance": int(account.referral_balance or 0),
                "percent": int(account.referral_percent or 0),
            },
        }


@router.post("/referral/withdraw")
async def mini_referral_withdraw(payload: CreateWithdrawalPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    amount = int(payload.amount or 0)
    method = (payload.method or "").strip()

    if amount < MIN_WITHDRAW_AMOUNT:
        raise HTTPException(400, f"Минимальная сумма вывода: {MIN_WITHDRAW_AMOUNT} RUB")
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


@router.post("/subscription/reissue")
async def mini_subscription_reissue(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        sub_service = SubscriptionService(session)
        vpn_service = VPNService(session, xray_auth_token=XRAY_AUTH_TOKEN)

        try:
            _ = await sub_service.get_active_subscription(user.id)
            await vpn_service.reissue_keys(user.id)
        except Exception as e:
            raise _map_service_error(e)

        token = await UserService(session).get_subscription_token(user.id)
        sub_url = f"https://{settings.PUBLIC_BASE_URL}/sub/{token}"

        return {"ok": True, "subscription_url": sub_url}
