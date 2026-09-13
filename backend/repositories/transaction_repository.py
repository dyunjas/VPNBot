from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import Transaction
from backend.core.logger_config import get_logger

logger = get_logger("transactions")


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        res = await self.session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        return res.scalar_one_or_none()

    async def get_by_id_with_user(self, transaction_id: int) -> Optional[Transaction]:
        res = await self.session.execute(
            select(Transaction)
            .options(selectinload(Transaction.user))
            .where(Transaction.id == transaction_id)
        )
        return res.scalar_one_or_none()

    async def get_by_provider_id(self, provider_transaction_id: str) -> Optional[Transaction]:
        res = await self.session.execute(
            select(Transaction)
            .where(Transaction.transaction_id == provider_transaction_id)
            # Older data may contain duplicate provider IDs. Prefer the
            # already-paid row, otherwise use the newest transaction.
            .order_by(Transaction.paid.desc(), Transaction.created_at.desc(), Transaction.id.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def get_by_provider_id_for_update(self, provider_transaction_id: str) -> Optional[Transaction]:
        res = await self.session.execute(
            select(Transaction)
            .where(Transaction.transaction_id == provider_transaction_id)
            .order_by(Transaction.paid.desc(), Transaction.created_at.desc(), Transaction.id.desc())
            .limit(1)
            .with_for_update()
        )
        return res.scalar_one_or_none()

    async def list_by_user_id(self, user_id: int) -> List[Transaction]:
        res = await self.session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
        )
        return res.scalars().all()

    async def get_last_by_user_id(self, user_id: int) -> Optional[Transaction]:
        res = await self.session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list_all(self) -> List[Transaction]:
        res = await self.session.execute(
            select(Transaction).order_by(Transaction.created_at.desc())
        )
        return res.scalars().all()

    async def create(
        self,
        *,
        user_id: int,
        provider_transaction_id: str,
        amount: Decimal | int | float,
        payment_system: str,
        created_at: datetime,
        paid: bool = False,
        paid_at: datetime | None = None,
    ) -> Transaction:
        tx = Transaction(
            user_id=user_id,
            transaction_id=provider_transaction_id,
            amount=Decimal(amount),
            payment_system=payment_system,
            created_at=created_at,
            paid=paid,
            paid_at=paid_at
        )
        self.session.add(tx)
        logger.info(
            "[transaction] created user_id=%s provider_id=%s payment_system=%s amount=%s paid=%s",
            user_id,
            provider_transaction_id,
            payment_system,
            amount,
            paid,
        )
        return tx

    async def mark_paid(
        self,
        *,
        provider_transaction_id: str,
        paid_at: datetime,
    ) -> int:
        res = await self.session.execute(
            update(Transaction)
            .where(Transaction.transaction_id == provider_transaction_id)
            .values(
                paid=True,
                paid_at=paid_at,
            )
        )
        updated = int(res.rowcount or 0)
        logger.info(
            "[transaction] payment_status_updated provider_id=%s paid=%s rows=%s",
            provider_transaction_id,
            updated > 0,
            updated,
        )
        return updated
