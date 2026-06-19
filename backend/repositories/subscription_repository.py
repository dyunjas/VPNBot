from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.database.models import SubscriptionPlan, Subscription, SubStatus


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_plans(self) -> Sequence[SubscriptionPlan]:
        res = await self.session.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.id.asc()))
        return res.scalars().all()
    
    async def get_plan_by_id(self, plan_id: int) -> SubscriptionPlan | None:
        res = await self.session.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        return res.scalar_one_or_none()
    
    async def get_by_user_id(self, user_id: int) -> Subscription | None:
        res = await self.session.execute(select(Subscription).where(Subscription.user_id == user_id))
        return res.scalar_one_or_none()
    
    async def get_by_id_for_update(self, user_id: int) -> Subscription | None:
        res = await self.session.execute(
            select(Subscription).where(Subscription.user_id == user_id).with_for_update()
        )
        return res.scalar_one_or_none()
    
    async def get_active_with_plan(self, user_id: int, now: datetime) -> Subscription | None:
        res = await self.session.execute(
            select(Subscription)
            .options(joinedload(Subscription.plan))
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubStatus.active,
                Subscription.current_period_end > now
            )
            .order_by(Subscription.current_period_end.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()
    
    async def create(
            self,
            *,
            user_id: int,
            plan_id: int,
            status: SubStatus,
            auto_renew: bool,
            current_period_start: datetime,
            current_period_end: datetime,
            next_renewal_at: datetime,
    ) -> Subscription:
        sub = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            auto_renew=auto_renew,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            next_renewal_at=next_renewal_at,
            gb_left=0,
        )
        self.session.add(sub)
        return sub
    
    async def set_plan_and_period(
            self,
            sub: Subscription,
            *,
            plan_id: int,
            status: SubStatus,
            auto_renew: bool,
            current_period_start: datetime,
            current_period_end: datetime,
            next_renewal_at: datetime,
    ) -> None:
        sub.plan_id = plan_id
        sub.status = status
        sub.auto_renew = auto_renew
        sub.current_period_start = current_period_start
        sub.current_period_end = current_period_end
        sub.next_renewal_at = next_renewal_at

    async def list_active_expired(self, *, now: datetime) -> list[Subscription]:
        res = await self.session.execute(
            select(Subscription).where(
                Subscription.status == SubStatus.active,
                Subscription.current_period_end < now
            )
        )
        return res.scalars().all()

    async def list_active_ending_between(
        self,
        *,
        start: datetime,
        end: datetime
    ) -> list[Subscription]:
        res = await self.session.execute(
            select(Subscription).where(
                Subscription.status == SubStatus.active,
                Subscription.current_period_end.between(start, end)
            )
        )
        return res.scalars().all()

    async def mark_expired(self, *, subscription_id: int) -> int:
        res = await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status=SubStatus.expired)
        )
        return int(res.rowcount or 0)

    async def set_auto_renew(self, *, subscription_id: int, auto_renew: bool) -> int:
        res = await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(auto_renew=auto_renew)
        )
        return int(res.rowcount or 0)

    async def set_subscription_token(self, *, subscription_id: int, token: str | None) -> int:
        res = await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(subscription_token=token)
        )
        return int(res.rowcount or 0)
