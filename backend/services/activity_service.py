from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import UserActivity


class ActivityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_user_event(
        self,
        *,
        user_id: int,
        category: str,
        action: str,
        source: str = "system",
        amount: int | None = None,
        traffic_gb: int | float | Decimal | None = None,
        subscription_id: int | None = None,
        transaction_id_ref: int | None = None,
        note: str | None = None,
    ) -> UserActivity:
        item = UserActivity(
            user_id=user_id,
            category=str(category or "system")[:32],
            action=str(action or "event")[:64],
            source=str(source or "system")[:32],
            amount=amount,
            traffic_gb=Decimal(str(traffic_gb)) if traffic_gb is not None else None,
            subscription_id=subscription_id,
            transaction_id_ref=transaction_id_ref,
            note=(str(note).strip()[:512] if note else None),
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_user_events(self, *, user_id: int, limit: int = 100) -> list[UserActivity]:
        rows = await self.session.execute(
            select(UserActivity)
            .where(UserActivity.user_id == user_id)
            .order_by(desc(UserActivity.created_at), desc(UserActivity.id))
            .limit(max(1, min(limit, 300)))
        )
        return list(rows.scalars().all())
