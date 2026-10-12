from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from api.cabinet.common import (
    BillingService,
    BuyDeviceSlotsPayload,
    BuySubscriptionPayload,
    BuyTrafficPayload,
    DeleteDevicePayload,
    GiftSubscriptionPayload,
    InitPayload,
    ReferralService,
    RemnaWaveService,
    SetAutoRenewPayload,
    SubscriptionNotFound,
    SubscriptionService,
    TransactionService,
    _get_user,
    _map_service_error,
    _resolve_request_user_id,
    async_session,
    require_optional_cabinet_auth,
)
from backend.services.exceptions import InsufficientBalance
from backend.core.business_config import get_business_decimal, get_business_int
from backend.services.payment_method_service import get_payment_method_config
from backend.database.models import User

router = APIRouter()


@router.post("/ui-config")
async def cabinet_ui_config(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        await _get_user(session, user_id)
        methods = []
        for provider in ("platega", "pally", "cryptobot"):
            config = await get_payment_method_config(session, provider)
            if provider == "platega" and config.get("merchant_id") and config.get("secret"):
                methods.extend(["platega-card", "platega-sbp"])
            elif provider == "pally" and config.get("api_token") and config.get("shop_id"):
                methods.append("pally")
            elif provider == "cryptobot" and config.get("api_token"):
                methods.append("crypto")
        return {
            "renewal_window_days": get_business_int("SUBSCRIPTION_RENEWAL_WINDOW_DAYS"),
            "traffic_price_per_gb": str(get_business_decimal("TRAFFIC_PRICE_PER_GB_RUB")),
            "min_traffic_purchase_gb": get_business_int("MIN_TRAFFIC_PURCHASE_GB"),
            "device_slot_price": str(get_business_decimal("DEVICE_SLOT_PRICE_RUB")),
            "payment_methods": methods,
        }


async def _find_gift_recipient(session, raw: str) -> User:
    value = (raw or "").strip().lstrip("@")
    if not value:
        raise HTTPException(status_code=400, detail="Укажите получателя")

    if "@" in value:
        res = await session.execute(select(User).where(User.email.ilike(value.lower())))
    elif value.lstrip("-").isdigit():
        res = await session.execute(select(User).where(User.tg_id == int(value)))
    else:
        res = await session.execute(select(User).where(User.username.ilike(value)))

    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Получатель не найден")
    if bool(getattr(user, "banned", False)):
        raise HTTPException(status_code=403, detail="Получатель заблокирован")
    return user


@router.post("/profile")
async def cabinet_profile(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
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
    user_id = await _resolve_request_user_id(payload.initData, user_id)
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
        sub_url = remnawave_service._normalize_subscription_url(
            remote.get("subscriptionUrl") or remote.get("subscription_url")
        )
        devices = await remnawave_service.get_user_hwid_devices(user=user)
        try:
            devices_limit = max(0, int(remote.get("hwidDeviceLimit"))) if remote.get("hwidDeviceLimit") is not None else 0
        except Exception:
            devices_limit = 0
        user_traffic = remote.get("userTraffic") if isinstance(remote.get("userTraffic"), dict) else {}
        renewal_end = active_sub.current_period_end
        if renewal_end and renewal_end.tzinfo is None:
            renewal_end = renewal_end.replace(tzinfo=timezone.utc)
        renewal_at = renewal_end - timedelta(days=get_business_int("SUBSCRIPTION_RENEWAL_WINDOW_DAYS")) if renewal_end else None
        return {
            "ok": True,
            "has_subscription": status in {"ACTIVE", "LIMITED"},
            "statusText": f"Статус: {status or 'UNKNOWN'}\nДействует до: {expire_at or '—'}",
            "active_keys": 0,
            "subscription_url": sub_url,
            "plan": None,
            "can_renew": renewal_at is None or datetime.now(timezone.utc) >= renewal_at,
            "renewal_available_at": renewal_at.isoformat() if renewal_at else None,
            "subscription": {
                "current_period_start": None,
                "current_period_end": expire_at,
                "status": status or None,
                "auto_renew": bool(active_sub.auto_renew),
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


@router.post("/subscription/auto-renew")
async def cabinet_subscription_auto_renew(
    payload: SetAutoRenewPayload,
    user_id: int | None = Depends(require_optional_cabinet_auth),
):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        try:
            sub = await SubscriptionService(session).set_auto_renew(
                user_id=user.id,
                auto_renew=payload.auto_renew,
            )
        except Exception as exc:
            raise _map_service_error(exc)
        return {
            "ok": True,
            "subscription": {
                "id": sub.id,
                "auto_renew": bool(sub.auto_renew),
                "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            },
        }


@router.post("/plans")
async def cabinet_plans(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        _ = await _get_user(session, user_id)
        plans = await SubscriptionService(session).list_plans()
        return {"ok": True, "plans": [{"id": p.id, "name": p.name, "price": p.price, "period_days": p.period_days, "gb_limit": int(getattr(p, "gb_limit", 0) or 0), "device_limit": int(getattr(p, "device_limit", 0) or 0), "created_at": p.created_at.isoformat() if p.created_at else None} for p in plans]}


@router.post("/subscription/buy")
async def cabinet_subscription_buy(payload: BuySubscriptionPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
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
    user_id = await _resolve_request_user_id(payload.initData, user_id)
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


@router.post("/subscription/devices/buy")
async def cabinet_subscription_devices_buy(payload: BuyDeviceSlotsPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        billing = BillingService(session)
        try:
            sub, charged = await billing.add_device_slots_to_subscription(user_id=user.id, slots=int(payload.slots))
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()
        return {
            "ok": True,
            "subscription_id": sub.id,
            "slots_added": int(payload.slots),
            "device_limit": int(sub.device_limit or 0),
            "charged": int(charged),
        }


@router.post("/subscription/gift")
async def cabinet_subscription_gift(payload: GiftSubscriptionPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    buyer_user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        buyer = await _get_user(session, buyer_user_id)
        recipient = await _find_gift_recipient(session, payload.recipient)
        if int(recipient.id) == int(buyer.id):
            raise HTTPException(status_code=400, detail="Для себя используйте обычную покупку подписки")
        billing = BillingService(session)
        try:
            sub, charged, recipient = await billing.gift_subscription(
                buyer_user_id=buyer.id,
                recipient_user_id=recipient.id,
                plan_id=payload.plan_id,
            )
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()
        return {
            "ok": True,
            "subscription_id": sub.id,
            "plan_id": sub.plan_id,
            "charged": int(charged),
            "recipient": {
                "id": recipient.id,
                "tg_id": recipient.tg_id,
                "username": recipient.username,
                "email": recipient.email,
            },
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        }


@router.post("/devices")
async def cabinet_devices(payload: InitPayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
    async with async_session() as session:
        user = await _get_user(session, user_id)
        devices = await RemnaWaveService(session).get_user_hwid_devices(user=user)
        return {"ok": True, "items": [{"id": i, "hwid": d.get("hwid"), "device_model": d.get("deviceModel"), "device_os": d.get("platform"), "os_version": d.get("osVersion"), "device_locale": None, "user_agent": d.get("userAgent"), "first_seen_at": d.get("createdAt"), "last_seen_at": d.get("updatedAt")} for i, d in enumerate(devices)]}


@router.post("/device/delete")
async def cabinet_device_delete(payload: DeleteDevicePayload, user_id: int | None = Depends(require_optional_cabinet_auth)):
    user_id = await _resolve_request_user_id(payload.initData, user_id)
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
