from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession


class SubscriptionTopupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_topup(self, *, subscription_id: int, gb: Decimal) -> None:
        return None

    async def sum_gb(self, *, subscription_id: int) -> Decimal:
        return Decimal(0)

    async def clear_for_subscription(self, *, subscription_id: int) -> int:
        return 0
