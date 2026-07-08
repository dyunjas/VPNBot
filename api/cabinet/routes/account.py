from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.cabinet.common import (
    BillingService,
    BuySubscriptionPayload,
    BuyTrafficPayload,
    DeleteDevicePayload,
    InitPayload,
    PromoService,
    ReferralService,
    RemnaWaveService,
    SubscriptionNotFound,
    SubscriptionService,
    TransactionService,
    UserService,
    WithdrawalService,
    _get_user,
    _map_service_error,
    _resolve_request_user_id,
    async_session,
    require_optional_cabinet_auth,
    settings,
)
from backend.services.exceptions import InsufficientBalance

router = APIRouter()


@router.post("/profile")
async def cabinet_profile(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        tx_service = TransactionService(session)
        referral_service = ReferralService(session)
        txs = (await tx_service.list_by_user(user.id))[:50]
        referral_account = await referral_service.get_account(user.id) or await referral_service.create_account(user.id)
        await session.commit()
        return {
            "ok": True,
            "user": {"tg_id": user.tg_id, "username": user.username, "balance": user.balance, "email": user.email, "created_at": user.created_at.isoformat() if user.created_at else None},
            "referral": {"balance": int(referral_account.referral_balance or 0), "percent": int(referral_account.referral_percent or 0), "invited_count": int(referral_account.invited_count or 0)},
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


@router.post("/status")
async def cabinet_status(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        sub_service = SubscriptionService(session)
        remnawave_service = RemnaWaveService(session)
        try:
            active_sub = await sub_service.get_active_subscription(user_id=user.id)
        except SubscriptionNotFound:
            return {"ok": True, "has_subscription": False, "statusText": "Нет активной подписки.", "active_keys": 0, "subscription_url": None}

        remote = await remnawave_service.get_user_snapshot(user=user)
        if not isinstance(remote, dict):
            return {"ok": True, "has_subscription": False, "statusText": "Нет активной подписки.", "active_keys": 0, "subscription_url": None}
        status = str(remote.get("status") or "")
        expire_at = remote.get("expireAt")
        sub_url = remote.get("subscriptionUrl") or remote.get("subscription_url")
        devices = await remnawave_service.get_user_hwid_devices(user=user)
        try:
            devices_limit = max(0, int(remote.get("hwidDeviceLimit"))) if remote.get("hwidDeviceLimit") is not None else 0
        except Exception:
            devices_limit = 0
        user_traffic = remote.get("userTraffic") if isinstance(remote.get("userTraffic"), dict) else {}
        return {
            "ok": True,
            "has_subscription": status in {"ACTIVE", "LIMITED"},
            "statusText": f"Статус: {status or 'UNKNOWN'}\nДействует до: {expire_at or '—'}",
            "active_keys": 0,
            "subscription_url": sub_url,
            "plan": None,
            "subscription": {
                "current_period_start": None,
                "current_period_end": expire_at,
                "status": status or None,
                "token": getattr(active_sub, "subscription_token", None),
                "gb_left": None,
                "devices_limit": devices_limit,
                "devices_used": len(devices),
                "devices_left": max(devices_limit - len(devices), 0) if devices_limit > 0 else None,
            },
            "remnawave": {
                "uuid": remote.get("uuid"),
                "id": remote.get("id"),
                "username": remote.get("username"),
                "trafficLimitBytes": remote.get("trafficLimitBytes"),
                "trafficLimitStrategy": remote.get("trafficLimitStrategy"),
                "usedTrafficBytes": user_traffic.get("usedTrafficBytes"),
                "lifetimeUsedTrafficBytes": user_traffic.get("lifetimeUsedTrafficBytes"),
                "hwidDeviceLimit": remote.get("hwidDeviceLimit"),
            },
        }


@router.post("/plans")
async def cabinet_plans(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        _ = await _get_user(session, user_id)
        plans = await SubscriptionService(session).list_plans()
        return {"ok": True, "plans": [{"id": p.id, "name": p.name, "price": p.price, "period_days": p.period_days, "gb_limit": int(getattr(p, "gb_limit", 0) or 0), "created_at": p.created_at.isoformat() if p.created_at else None} for p in plans]}


@router.post("/subscription/buy")
async def cabinet_subscription_buy(payload: BuySubscriptionPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        try:
            await SubscriptionService(session).get_public_plan(payload.plan_id)
        except Exception as e:
            raise _map_service_error(e)
        billing = BillingService(session)
        try:
            sub = await billing.buy_subscription(user_id=user.id, plan_id=payload.plan_id, auto_renew=True)
        except InsufficientBalance:
            raise HTTPException(status_code=409, detail="Недостаточно средств на балансе. Пополните баланс.")
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()
        plan = await SubscriptionService(session).get_plan(sub.plan_id)
        return {"ok": True, "subscription": {"id": sub.id, "plan_id": plan.id, "plan_name": plan.name, "current_period_start": sub.current_period_start.isoformat(), "current_period_end": sub.current_period_end.isoformat(), "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status)}}


@router.post("/subscription/traffic/buy")
async def cabinet_subscription_traffic_buy(payload: BuyTrafficPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    if payload.gb <= 0:
        raise HTTPException(status_code=400, detail="Введите количество ГБ больше 0")
    async with async_session() as session:
        user = await _get_user(session, user_id)
        billing = BillingService(session)
        try:
            sub, charged = await billing.add_gb_to_subscription(user_id=user.id, gb=int(payload.gb))
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()
        return {"ok": True, "subscription_id": sub.id, "gb_added": int(payload.gb), "charged": int(charged)}


@router.post("/devices")
async def cabinet_devices(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        devices = await RemnaWaveService(session).get_user_hwid_devices(user=user)
        return {"ok": True, "items": [{"id": i, "hwid": d.get("hwid"), "device_model": d.get("deviceModel"), "device_os": d.get("platform"), "os_version": d.get("osVersion"), "device_locale": None, "user_agent": d.get("userAgent"), "first_seen_at": d.get("createdAt"), "last_seen_at": d.get("updatedAt")} for i, d in enumerate(devices)]}


@router.post("/device/delete")
async def cabinet_device_delete(payload: DeleteDevicePayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        remn = RemnaWaveService(session)
        devices = await remn.get_user_hwid_devices(user=user)
        if payload.device_id < 0 or payload.device_id >= len(devices):
            raise HTTPException(status_code=404, detail="device not found")
        hwid = str(devices[payload.device_id].get("hwid") or "").strip()
        if not hwid:
            raise HTTPException(status_code=404, detail="device not found")
        if not await remn.delete_hwid_device(user=user, hwid=hwid):
            raise HTTPException(status_code=502, detail="remnawave delete device failed")
        return {"ok": True, "deleted_device_id": payload.device_id}
