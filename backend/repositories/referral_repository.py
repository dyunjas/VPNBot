from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ReferralAccount, User


class ReferralRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_account(self, user_id: int) -> None:
        account = ReferralAccount(user_id=user_id)
        self.session.add(account)
        return account

    async def set_referrer_if_empty(
            self,
            *,
            user_id: int,
            referrer_id: int
    ) -> int:
        res = await self.session.execute(
            update(User)
            .where(
                User.id == user_id,
                User.referrer_id.is_(None)
            )
            .values(referrer_id=referrer_id)
        )
        return int(res.rowcount or 0)
    
    async def increase_invited_count(
        self,
        referrer_id: int
    ) -> None:
        await self.session.execute(
            update(ReferralAccount)
            .where(ReferralAccount.user_id == referrer_id)
            .values(
                invited_count=ReferralAccount.invited_count + 1
            )
        )

    async def add_referral_balance(
        self,
        *,
        user_id: int,
        amount: int
    ) -> None:
        await self.session.execute(
            update(ReferralAccount)
            .where(ReferralAccount.user_id == user_id)
            .values(
                referral_balance=ReferralAccount.referral_balance + amount
            )
        )
    
    async def get_account(self, user_id: int) -> ReferralAccount | None:
        res = await self.session.execute(
            select(ReferralAccount)
            .where(ReferralAccount.user_id == user_id)
        )
        return res.scalar_one_or_none()
    
    async def decrease_balance_if_enough(
            self,
            *,
            user_id: int,
            amount: int
    ) -> int:
        res = await self.session.execute(
            update(ReferralAccount)
            .where(
                ReferralAccount.user_id == user_id,
                ReferralAccount.referral_balance >= amount
            )
            .values(
                referral_balance=ReferralAccount.referral_balance - amount
            )
        )
        return int(res.rowcount or 0)
