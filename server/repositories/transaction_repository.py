from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from server.database.models import Transaction, User


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_transaction(
        self,
        tg_id: int,
        transaction_id: str,
        amount: int,
        payment_system: str,
        order_id: str,
        created_at: datetime | None = None,
    ) -> Transaction:
        stmt = select(User).where(User.tg_id == tg_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User with tg_id={tg_id} not found")

        transaction = Transaction(
            transaction_id=transaction_id,
            amount=amount,
            payment_system=payment_system,
            user_id=user.id,
            order_id=order_id,
            created_at=created_at or datetime.now()
        )
        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction

    async def get_transactions(self, tg_id: int) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .join(User)
            .where(User.tg_id == tg_id)
            .order_by(Transaction.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_transaction_by_id(self, transaction_id: int) -> Transaction | None:
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.user))
            .where(Transaction.id == transaction_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_transaction_by_payment_system_id(self, transaction_id: str) -> Transaction | None:
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.user))
            .where(Transaction.transaction_id == transaction_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def mark_transaction_as_paid(self, transaction_id: str, paid_at: datetime | None = None) -> None:
        stmt = (
            select(Transaction)
            .where(Transaction.transaction_id == transaction_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        transaction = result.scalar_one_or_none()
        if not transaction:
            return
        
        transaction.paid = True
        transaction.paid_at = paid_at or datetime.now()
        await self.session.commit()

    async def get_last_transaction(self, tg_id: int) -> Transaction | None:
        stmt = (
            select(Transaction)
            .join(User)
            .where(User.tg_id == tg_id)
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_transactions(self):
        result = await self.session.execute(
            select(Transaction)
            .order_by(Transaction.created_at.desc()))
        return result.scalars().all()
