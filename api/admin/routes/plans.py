from fastapi import APIRouter
from sqlalchemy.exc import IntegrityError
from ..common import *

router = APIRouter()

@router.get("/plans", dependencies=[Depends(require_admin_auth)])
async def admin_plans(
    sort_by: str = Query(default="id"),
    sort_dir: Literal["asc", "desc"] = Query(default="asc"),
):
    sort_column = PLAN_SORT_FIELDS.get(sort_by, SubscriptionPlan.id)
    order_by = desc(sort_column) if sort_dir == "desc" else sort_column.asc()

    async with async_session() as session:
        plans = list((await session.execute(select(SubscriptionPlan).order_by(order_by))).scalars().all())
        sub_counts = {
            int(pid): int(cnt)
            for pid, cnt in (
                await session.execute(
                    select(Subscription.plan_id, func.count(Subscription.id)).group_by(Subscription.plan_id)
                )
            ).all()
        }

    return {
        "ok": True,
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "price": int(p.price),
                "period_days": p.period_days,
                "gb_limit": int(getattr(p, "gb_limit", 0) or 0),
                "created_at": _to_iso(p.created_at),
                "subscriptions_count": sub_counts.get(p.id, 0),
            }
            for p in plans
        ],
    }


@router.post("/plans", dependencies=[Depends(require_admin_auth)])
async def admin_plan_create(payload: PlanCreatePayload):
    async with async_session() as session:
        exists = await session.scalar(select(SubscriptionPlan.id).where(SubscriptionPlan.name == payload.name))
        if exists:
            raise HTTPException(status_code=400, detail="plan with this name already exists")
        plan = SubscriptionPlan(
            name=payload.name.strip(),
            price=payload.price,
            period_days=payload.period_days,
            gb_limit=payload.gb_limit,
            created_at=datetime.now(timezone.utc),
        )
        session.add(plan)
        await session.commit()
        await session.refresh(plan)
        return {"ok": True, "plan_id": plan.id}


@router.patch("/plans/{plan_id}", dependencies=[Depends(require_admin_auth)])
async def admin_plan_update(plan_id: int, payload: PlanUpdatePayload):
    async with async_session() as session:
        plan = _http_404_if_none(await session.get(SubscriptionPlan, plan_id), "plan not found")
        if payload.name is not None:
            name = payload.name.strip()
            exists = await session.scalar(
                select(SubscriptionPlan.id).where(SubscriptionPlan.name == name, SubscriptionPlan.id != plan_id)
            )
            if exists:
                raise HTTPException(status_code=400, detail="plan with this name already exists")
            plan.name = name
        if payload.price is not None:
            plan.price = payload.price
        if payload.period_days is not None:
            plan.period_days = payload.period_days
        if payload.gb_limit is not None:
            plan.gb_limit = payload.gb_limit
        await session.commit()
        await session.refresh(plan)
        return {"ok": True}


@router.delete("/plans/{plan_id}", dependencies=[Depends(require_admin_auth)])
async def admin_plan_delete(plan_id: int):
    async with async_session() as session:
        plan = _http_404_if_none(await session.get(SubscriptionPlan, plan_id), "plan not found")
        await session.delete(plan)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=400,
                detail="cannot delete plan with linked entities",
            )
        return {"ok": True}


