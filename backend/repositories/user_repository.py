from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        res = await self.session.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        res = await self.session.execute(select(User).where(User.email == email))
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

    async def set_email(
            self,
            *,
            user_id: int,
            email: str | None
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(email=email)
        )

    async def set_traffic_limit_bytes(
        self,
        *,
        user_id: int,
        traffic_limit_bytes: int,
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(traffic_limit_bytes=max(0, int(traffic_limit_bytes or 0)))
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

    async def set_subscription_url(
        self,
        *,
        user_id: int,
        subscription_url: str | None,
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(subscription_url=subscription_url)
        )

    async def set_remnawave_binding(
        self,
        *,
        user_id: int,
        remnawave_user_id: int | None = None,
        remnawave_user_uuid: str | None = None,
        subscription_url: str | None = None,
    ) -> None:
        values: dict = {}
        if remnawave_user_id is not None:
            values["remnawave_user_id"] = remnawave_user_id
        if remnawave_user_uuid:
            values["remnawave_user_uuid"] = remnawave_user_uuid
        if subscription_url is not None:
            values["subscription_url"] = subscription_url
        if not values:
            return
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(**values)
        )
    
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
