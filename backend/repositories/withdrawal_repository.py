from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import (
    ReferralWithdrawal,
    WithdrawalStatus,
    ReferralAccount,
)


class WithdrawalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_withdrawal(
        self,
        *,
        referral_account_id: int,
        amount: int,
        method: str
    ) -> ReferralWithdrawal:
        withdrawal = ReferralWithdrawal(
            referral_account_id=referral_account_id,
            amount=amount,
            method=method,
            status=WithdrawalStatus.pending,
        )
        self.session.add(withdrawal)
        return withdrawal

    async def get_by_id(self, withdrawal_id: int) -> ReferralWithdrawal | None:
        res = await self.session.execute(
            select(ReferralWithdrawal)
            .where(ReferralWithdrawal.id == withdrawal_id)
            .options(
                selectinload(ReferralWithdrawal.referral_account)
                .selectinload(ReferralAccount.user)
            )
        )
        return res.scalar_one_or_none()

    async def list_pending(self, limit: int = 100) -> list[ReferralWithdrawal]:
        res = await self.session.execute(
            select(ReferralWithdrawal)
            .where(ReferralWithdrawal.status == WithdrawalStatus.pending)
            .order_by(ReferralWithdrawal.created_at.asc())
            .limit(limit)
            .options(
                selectinload(ReferralWithdrawal.referral_account)
                .selectinload(ReferralAccount.user)
            )
        )
        return list(res.scalars().all())

    async def list_by_user_id(self, *, user_id: int, limit: int = 30) -> list[ReferralWithdrawal]:
        res = await self.session.execute(
            select(ReferralWithdrawal)
            .join(ReferralAccount, ReferralAccount.id == ReferralWithdrawal.referral_account_id)
            .where(ReferralAccount.user_id == user_id)
            .order_by(ReferralWithdrawal.created_at.desc())
            .limit(limit)
            .options(
                selectinload(ReferralWithdrawal.referral_account)
                .selectinload(ReferralAccount.user)
            )
        )
        return list(res.scalars().all())

    async def set_status_if_pending(
        self,
        *,
        withdrawal_id: int,
        status: WithdrawalStatus
    ) -> int:
        res = await self.session.execute(
            update(ReferralWithdrawal)
            .where(
                ReferralWithdrawal.id == withdrawal_id,
                ReferralWithdrawal.status == WithdrawalStatus.pending,
            )
            .values(status=status)
        )
        return int(res.rowcount or 0)
