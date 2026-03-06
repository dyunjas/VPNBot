from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import SubscriptionTopup


class SubscriptionTopupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_topup(self, *, subscription_id: int, gb: Decimal) -> SubscriptionTopup:
        topup = SubscriptionTopup(subscription_id=subscription_id, gb_added=gb)
        self.session.add(topup)
        return topup

    async def sum_gb(self, *, subscription_id: int) -> Decimal:
        res = await self.session.execute(
            select(func.coalesce(func.sum(SubscriptionTopup.gb_added), 0))
            .where(SubscriptionTopup.subscription_id == subscription_id)
        )
        total = res.scalar_one()
        return Decimal(total or 0)

    async def clear_for_subscription(self, *, subscription_id: int) -> int:
        res = await self.session.execute(
            delete(SubscriptionTopup).where(SubscriptionTopup.subscription_id == subscription_id)
        )
        return int(res.rowcount or 0)
