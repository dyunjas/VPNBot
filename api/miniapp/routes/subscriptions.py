from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from backend.database.models import User

from ..common import *

router = APIRouter()


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
                    "gb_limit": int(getattr(p, "gb_limit", 0) or 0),
                    "device_limit": int(getattr(p, "device_limit", 0) or 0),
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
        sub_service = SubscriptionService(session)

        try:
            await sub_service.get_public_plan(payload.plan_id)
            sub = await billing.buy_subscription(
                user_id=user.id,
                plan_id=payload.plan_id,
                auto_renew=True,
            )
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()

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


@router.post("/subscription/traffic/buy")
async def mini_subscription_traffic_buy(payload: BuyTrafficPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]
    if payload.gb <= 0:
        raise HTTPException(400, "Введите количество ГБ больше 0")

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        billing = BillingService(session)
        try:
            sub, charged = await billing.add_gb_to_subscription(
                user_id=user.id,
                gb=int(payload.gb),
            )
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()

        return {
            "ok": True,
            "subscription_id": sub.id,
            "gb_added": int(payload.gb),
            "charged": int(charged),
        }


@router.post("/subscription/devices/buy")
async def mini_subscription_devices_buy(payload: BuyDeviceSlotsPayload):
    tg_user = _get_tg_user(payload.initData)
    if payload.slots <= 0:
        raise HTTPException(400, "Количество устройств должно быть больше нуля")
    async with async_session() as session:
        user = await _get_user_or_404(session, tg_user["id"])
        billing = BillingService(session)
        try:
            sub, charged = await billing.add_device_slots_to_subscription(user_id=user.id, slots=int(payload.slots))
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()
        return {"ok": True, "subscription_id": sub.id, "slots_added": int(payload.slots), "device_limit": int(sub.device_limit or 0), "charged": int(charged)}


@router.post("/subscription/gift")
async def mini_subscription_gift(payload: GiftSubscriptionPayload):
    tg_user = _get_tg_user(payload.initData)
    recipient_value = (payload.recipient or "").strip().lstrip("@")
    if not recipient_value:
        raise HTTPException(400, "Укажите получателя подарка")
    async with async_session() as session:
        buyer = await _get_user_or_404(session, tg_user["id"])
        query = select(User).where(User.tg_id == int(recipient_value)) if recipient_value.lstrip("-").isdigit() else select(User).where(User.username.ilike(recipient_value))
        recipient = (await session.execute(query)).scalar_one_or_none()
        if not recipient:
            raise HTTPException(404, "Получатель не найден")
        if recipient.id == buyer.id:
            raise HTTPException(400, "Нельзя подарить подписку самому себе")
        billing = BillingService(session)
        try:
            sub, charged, recipient = await billing.gift_subscription(buyer_user_id=buyer.id, recipient_user_id=recipient.id, plan_id=payload.plan_id)
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()
        return {"ok": True, "subscription_id": sub.id, "charged": int(charged), "recipient": {"tg_id": recipient.tg_id, "username": recipient.username}}
