from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from server.database.models import (
    SubscriptionPlan, Subscription,
    User, SubStatus
)

from datetime import datetime, timedelta

from decimal import Decimal

from sqlalchemy.orm import joinedload

class NotEnoughBalanceError(Exception):
    pass

class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_subscription_plans(self):
        result = await self.session.execute(select(SubscriptionPlan))
        return result.scalars().all()
    
    async def get_subscription_plan_by_id(self, plan_id: int):
        result = await self.session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        return result.scalar_one_or_none()
    
    async def create_or_renew_subscription(self, tg_id: int, plan_id: int) -> Subscription:
        user_result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        plan = await self.session.get(SubscriptionPlan, plan_id)
        if not plan:
            raise ValueError("Plan not found")

        if user.balance < plan.price:
            raise NotEnoughBalanceError("Not enough balance")

        user.balance -= plan.price

        now = datetime.now()
        period = timedelta(days=plan.period_days)

        subscription_result = await self.session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscription = subscription_result.scalar_one_or_none()

        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status=SubStatus.active,
                auto_renew=True,
                current_period_start=now,
                current_period_end=now + period,
                next_renewal_at=now + period,
            )
            self.session.add(subscription)
        else:
            if subscription.status == SubStatus.active and subscription.current_period_end > now:
                subscription.plan_id = plan.id
                subscription.current_period_end = subscription.current_period_end + period
                subscription.next_renewal_at = subscription.current_period_end
            else:
                subscription.plan_id = plan.id
                subscription.status = SubStatus.active
                subscription.current_period_start = now
                subscription.current_period_end = now + period
                subscription.next_renewal_at = subscription.current_period_end

        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription
    
    async def get_active_subscription_with_plan_by_tg(self, tg_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription)
            .join(User)
            .options(joinedload(Subscription.plan))
            .where(
                User.tg_id == tg_id,
                Subscription.status == SubStatus.active,
                Subscription.current_period_end > datetime.now()
            )
            .order_by(Subscription.current_period_end.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_user_subscription_by_tg_id(self, tg_id: int):
        result = await self.session.execute(
            select(Subscription)
            .join(User)
            .options(joinedload(Subscription.plan))
            .where(User.tg_id == tg_id, Subscription.status == SubStatus.active)
            .order_by(Subscription.current_period_end.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def increase_gb_amount(self, tg_id: int, amount: Decimal) -> Decimal:
        user_result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user_result.scalar_one_or_none()

        subscription_result = await self.session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscription = subscription_result.scalar_one_or_none()

        subscription.gb_left = Decimal(str(subscription.gb_left or 0)) + amount

        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription.gb_left