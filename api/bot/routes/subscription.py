from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.bot.common import (
    AutoRenewPayload,
    PlanBuyPayload,
    PromocodePayload,
    SubscriptionNotFound,
    TrafficBuyPayload,
    _get_user_or_404,
    _map_service_error,
    get_user_service,
    require_bot_auth,
)
from backend.services import BillingService, PromoService, RemnaWaveService, SubscriptionService

router = APIRouter(dependencies=[Depends(require_bot_auth)])


@router.get("/users/by-tg/{tg_id}/plans")
async def plans(tg_id: int, user_service=Depends(get_user_service)):
    _ = await _get_user_or_404(user_service, tg_id)
    plans = await SubscriptionService(user_service.session).list_plans()
    return {
        "ok": True,
        "items": [
            {
                "id": plan.id,
                "name": plan.name,
                "price": int(plan.price),
                "period_days": plan.period_days,
                "gb_limit": int(getattr(plan, "gb_limit", 0) or 0),
                "device_limit": int(getattr(plan, "device_limit", 0) or 0),
            }
            for plan in plans
        ],
    }


@router.get("/users/by-tg/{tg_id}/subscription")
async def subscription(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    sub_service = SubscriptionService(user_service.session)
    remnawave_service = RemnaWaveService(user_service.session)
    try:
        sub = await sub_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        sub = await sub_service.sub_repo.get_by_user_id(user.id)
        if not sub:
            raise HTTPException(status_code=404, detail="subscription not found")
    url = await remnawave_service.get_subscription_url(user=user, subscription=sub)
    return {"ok": True, "subscription": {"id": sub.id, "plan_id": sub.plan_id, "status": sub.status.value if sub.status else None, "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None, "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None, "auto_renew": bool(sub.auto_renew)}, "subscription_url": url}


@router.post("/users/by-tg/{tg_id}/subscription/buy")
async def subscription_buy(tg_id: int, payload: PlanBuyPayload, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    try:
        await SubscriptionService(user_service.session).get_public_plan(payload.plan_id)
    except Exception as e:
        raise _map_service_error(e)
    billing = BillingService(user_service.session)
    try:
        sub = await billing.buy_subscription(user_id=user.id, plan_id=payload.plan_id, auto_renew=payload.auto_renew)
    except Exception as e:
        raise _map_service_error(e)
    return {"ok": True, "subscription": {"id": sub.id, "plan_id": sub.plan_id, "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None, "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None}}


@router.post("/users/by-tg/{tg_id}/subscription/traffic")
async def subscription_traffic(tg_id: int, payload: TrafficBuyPayload, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    billing = BillingService(user_service.session)
    try:
        sub, charged = await billing.add_gb_to_subscription(user_id=user.id, gb=payload.gb)
    except Exception as e:
        raise _map_service_error(e)
    return {"ok": True, "subscription_id": sub.id, "gb_added": payload.gb, "charged": charged}


@router.post("/users/by-tg/{tg_id}/subscription/auto-renew")
async def subscription_auto_renew(tg_id: int, payload: AutoRenewPayload, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    try:
        sub = await SubscriptionService(user_service.session).set_auto_renew(user_id=user.id, auto_renew=payload.auto_renew)
    except Exception as e:
        raise _map_service_error(e)
    return {"ok": True, "subscription": {"id": sub.id, "plan_id": sub.plan_id, "auto_renew": bool(sub.auto_renew), "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None}}


@router.get("/users/by-tg/{tg_id}/subscription/url")
async def subscription_url(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    sub_service = SubscriptionService(user_service.session)
    remnawave_service = RemnaWaveService(user_service.session)
    try:
        sub = await sub_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        raise HTTPException(status_code=404, detail="active subscription not found")
    url = await remnawave_service.get_subscription_url(user=user, subscription=sub)
    return {"ok": True, "subscription_url": url, "subscription": {"id": sub.id, "plan_id": sub.plan_id, "status": sub.status.value if sub.status else None, "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None, "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None, "auto_renew": bool(sub.auto_renew)}}


@router.get("/users/by-tg/{tg_id}/devices")
async def devices(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    devices = await RemnaWaveService(user_service.session).get_user_hwid_devices(user=user)
    return {"ok": True, "items": [{"id": i, "hwid": d.get("hwid"), "device_model": d.get("deviceModel"), "device_os": d.get("platform"), "os_version": d.get("osVersion"), "user_agent": d.get("userAgent"), "first_seen_at": d.get("createdAt"), "last_seen_at": d.get("updatedAt")} for i, d in enumerate(devices)]}


@router.delete("/users/by-tg/{tg_id}/devices/{device_id}")
async def delete_device(tg_id: int, device_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    remnawave_service = RemnaWaveService(user_service.session)
    devices = await remnawave_service.get_user_hwid_devices(user=user)
    if device_id < 0 or device_id >= len(devices):
        raise HTTPException(status_code=404, detail="device not found")
    hwid = str(devices[device_id].get("hwid") or "").strip()
    if not hwid:
        raise HTTPException(status_code=404, detail="device not found")
    ok = await remnawave_service.delete_hwid_device(user=user, hwid=hwid)
    if not ok:
        raise HTTPException(status_code=502, detail="remnawave delete device failed")
    return {"ok": True, "deleted_device_id": device_id}


@router.post("/users/by-tg/{tg_id}/promocode")
async def promocode_apply(tg_id: int, payload: PromocodePayload, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    try:
        promo = await PromoService(user_service.session).activate_promocode(user_id=user.id, code=payload.code)
    except Exception as e:
        raise _map_service_error(e)
    fresh_user = await user_service.get_by_id(user.id)
    return {"ok": True, "amount_added": int(promo.amount or 0), "balance": int(fresh_user.balance or 0)}
