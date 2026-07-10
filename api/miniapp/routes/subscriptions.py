from fastapi import APIRouter

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
