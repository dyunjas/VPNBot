from __future__ import annotations

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import User, Key, ReferralAccount

import uuid


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        res = await self.session.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()
    
    async def get_by_tg_id_for_update(self, tg_id: int) -> User | None:
        res = await self.session.execute(
            select(User).where(User.tg_id == tg_id).with_for_update()
        )
        return res.scalar_one_or_none()
    
    async def get_by_id(self, user_id: int) -> User | None:
        res = await self.session.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()
    
    async def get_by_id_for_update(self, user_id: int) -> User| None:
        res = await self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        return res.scalar_one_or_none()

    async def get_by_id_for_update_nowait(self, user_id: int) -> User | None:
        res = await self.session.execute(
            select(User).where(User.id == user_id).with_for_update(nowait=True)
        )
        return res.scalar_one_or_none()
    
    async def create(
            self,
            *,
            tg_id: int,
            username: str | None
    ) -> User:
        user = User(
            tg_id=tg_id,
            username=username,
            balance=0,
            subscription_token=str(uuid.uuid4())
        )
        return user
    
    async def set_username(
            self,
            *,
            user_id: int,
            username: str | None
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(username=username)
        )
    
    async def add_balance(
            self,
            *,
            user_id: int,
            amount: int
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(balance=User.balance + amount)
        )

    async def sub_balance(
            self,
            *,
            user_id: int,
            amount: int
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(balance=User.balance - amount)
        )

    async def delete_key_by_id(self, key_id: int) -> int:
        res = await self.session.execute(delete(Key).where(Key.id == key_id))
        return int(res.rowcount or 0)

    async def set_subscription_token(
        self,
        *,
        user_id: int,
        token: str | None = None
    ) -> None:
        if token is None:
            token = str(uuid.uuid4())

        await self.session.execute(
            update(User)
            .where(User.id == user_id, User.subscription_token.is_(None))
            .values(subscription_token=token)
        )

    async def reissue_subscription_token(
        self,
        *,
        user_id: int,
        token: str | None = None,
    ) -> str:
        if token is None:
            token = str(uuid.uuid4())

        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(subscription_token=token)
        )
        return token

    async def get_user_by_token(self, token: str) -> User | None:
        res = await self.session.execute(
            select(User).where(User.subscription_token == token)
        )
        return res.scalar_one_or_none()
    
    async def set_refferal_if_empty(
            self, 
            *, 
            user_id: int, 
            referrer_id: int
        ) -> int:
        res = await self.session.execute(
            update(User)
            .where(User.id == user_id, User.referrer_id.is_(None))
            .values(referrer_id=referrer_id)
        )
        return int(res.rowcount or 0)
    
    async def set_referrer(
            self,
            *,
            user_id: int,
            referrer_id: int
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(referrer_id=referrer_id)
        )

    async def get_all_users(self):
        res = await self.session.execute(select(User))
        return list(res.scalars().all())
