from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import SubStatus
from backend.repositories.subscription_repository import SubscriptionRepository
from backend.repositories.user_repository import UserRepository
from backend.services.exceptions import (
    UserNotFound,
    SubscriptionNotFound,
    PlanNotFound,
)


class SubscriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sub_repo = SubscriptionRepository(session)
        self.user_repo = UserRepository(session)

    async def list_plans(self):
        return await self.sub_repo.list_plans()

    async def get_plan(self, plan_id: int):
        plan = await self.sub_repo.get_plan_by_id(plan_id)
        if not plan:
            raise PlanNotFound("Plan not found")
        return plan

    async def get_active_subscription(self, user_id: int):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        return await self.sub_repo.get_active_with_plan(
            user_id,
            now=datetime.now(timezone.utc),
        )

    async def activate_subscription(
        self,
        user_id: int,
        plan_id: int,
        auto_renew: bool,
    ):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        plan = await self.get_plan(plan_id)

        now = datetime.now(timezone.utc)
        period = timedelta(days=plan.period_days)

        sub = await self.sub_repo.get_by_id_for_update(user_id)

        if not sub:
            sub = await self.sub_repo.create(
                user_id=user_id,
                plan_id=plan.id,
                status=SubStatus.active,
                auto_renew=auto_renew,
                current_period_start=now,
                current_period_end=now + period,
                next_renewal_at=now + period,
            )
            await self.sub_repo.add_gb_left(sub, Decimal(plan.gb_limit))
        else:
            await self.sub_repo.set_plan_and_period(
                sub,
                plan_id=plan.id,
                status=SubStatus.active,
                auto_renew=auto_renew,
                current_period_start=now,
                current_period_end=now + period,
                next_renewal_at=now + period,
            )
            await self.sub_repo.add_gb_left(sub, Decimal(plan.gb_limit))

        if not user.subscription_token:
            await self.user_repo.set_subscription_token(user_id=user.id)

        return sub

    async def add_traffic(self, user_id: int, gb: Decimal):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        sub = await self.get_active_subscription(user_id)
        if not sub:
            raise SubscriptionNotFound("Subscription not found")

        await self.sub_repo.add_gb_left(sub, gb)
        return sub
    
    async def list_active_expired(self, *, now: datetime):
        return await self.sub_repo.list_active_expired(now=now)

    async def list_active_ending_between(self, *, start: datetime, end: datetime):
        return await self.sub_repo.list_active_ending_between(start=start, end=end)

    async def mark_expired(self, *, subscription_id: int) -> None:
        updated = await self.sub_repo.mark_expired(subscription_id=subscription_id)
        if updated <= 0:
            raise SubscriptionNotFound("Subscription not found")
        await self.session.commit()
    
    
