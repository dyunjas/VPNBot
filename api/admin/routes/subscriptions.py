from fastapi import APIRouter
from ..common import *

router = APIRouter()

@router.get("/subscriptions", dependencies=[Depends(require_admin_auth)])
async def admin_subscriptions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    status: Literal["all", "active", "past_due", "expired", "canceled"] = Query(default="all"),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="current_period_end"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
):
    sort_column = SUB_SORT_FIELDS.get(sort_by, Subscription.current_period_end)
    order_by = desc(sort_column) if sort_dir == "desc" else sort_column.asc()
    offset = (page - 1) * page_size

    async with async_session() as session:
        stmt = (
            select(Subscription, User.tg_id, User.username, SubscriptionPlan.name)
            .join(User, User.id == Subscription.user_id)
            .join(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id)
        )
        count_stmt = select(func.count(Subscription.id))

        if status != "all":
            stmt = stmt.where(Subscription.status == SubStatus(status))
            count_stmt = count_stmt.where(Subscription.status == SubStatus(status))

        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            search_clause = or_(
                cast(Subscription.user_id, String).ilike(pattern),
                cast(User.tg_id, String).ilike(pattern),
                func.coalesce(User.username, "").ilike(pattern),
            )
            stmt = stmt.where(search_clause)
            count_stmt = count_stmt.join(User, User.id == Subscription.user_id).where(search_clause)

        total = int(await session.scalar(count_stmt) or 0)
        rows = (await session.execute(stmt.order_by(order_by).offset(offset).limit(page_size))).all()

    return {
        "ok": True,
        "items": [
            {
                "id": sub.id,
                "user_id": sub.user_id,
                "tg_id": tg_id,
                "username": username,
                "plan_id": sub.plan_id,
                "plan_name": plan_name,
                "status": sub.status.value if sub.status else None,
                "auto_renew": bool(sub.auto_renew),
                "current_period_start": _to_iso(sub.current_period_start),
                "current_period_end": _to_iso(sub.current_period_end),
                "created_at": _to_iso(sub.created_at),
            }
            for sub, tg_id, username, plan_name in rows
        ],
        "meta": {"page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size},
    }


@router.post("/subscriptions", dependencies=[Depends(require_admin_auth)])
async def admin_subscription_create(payload: SubscriptionCreatePayload):
    async with async_session() as session:
        user = _http_404_if_none(await session.get(User, payload.user_id), "user not found")
        if user.banned:
            raise HTTPException(status_code=400, detail="cannot create subscription for banned user")

        sub_service = SubscriptionService(session)
        try:
            sub = await sub_service.activate_subscription(
                user_id=payload.user_id,
                plan_id=payload.plan_id,
                auto_renew=payload.auto_renew,
            )
            await session.commit()
            await session.refresh(sub)
            return {"ok": True, "subscription_id": sub.id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.patch("/subscriptions/{subscription_id}", dependencies=[Depends(require_admin_auth)])
async def admin_subscription_update(subscription_id: int, payload: SubscriptionUpdatePayload):
    async with async_session() as session:
        sub = _http_404_if_none(await session.get(Subscription, subscription_id), "subscription not found")
        user = _http_404_if_none(await session.get(User, sub.user_id), "user not found")
        now = datetime.now(timezone.utc)
        period_end_changed = False

        if payload.plan_id is not None:
            plan = _http_404_if_none(await session.get(SubscriptionPlan, payload.plan_id), "plan not found")
            sub.plan_id = plan.id

        if payload.status is not None:
            sub.status = SubStatus(payload.status)
        if payload.auto_renew is not None:
            sub.auto_renew = payload.auto_renew

        if payload.extend_days is not None:
            base_end = _as_aware_utc(sub.current_period_end) or now
            if base_end < now:
                base_end = now
            sub.current_period_end = base_end + timedelta(days=max(payload.extend_days, 0))
            sub.next_renewal_at = sub.current_period_end
            period_end_changed = True

        if payload.current_period_end is not None:
            sub.current_period_end = _as_aware_utc(payload.current_period_end)
            sub.next_renewal_at = sub.current_period_end
            period_end_changed = True

        await session.commit()
        if period_end_changed:
            remnawave_service = RemnaWaveService(session)
            if remnawave_service.enabled:
                try:
                    await remnawave_service.sync_subscription_expire_at(user=user, subscription=sub)
                except Exception:
                    pass
        await session.refresh(sub)
        return {"ok": True}


@router.delete("/subscriptions/{subscription_id}", dependencies=[Depends(require_admin_auth)])
async def admin_subscription_delete(subscription_id: int):
    async with async_session() as session:
        sub = _http_404_if_none(await session.get(Subscription, subscription_id), "subscription not found")
        await session.delete(sub)
        await session.commit()
        return {"ok": True}


