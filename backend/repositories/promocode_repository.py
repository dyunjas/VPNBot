from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Promocode, PromocodeActivation


class PromocodeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> Promocode | None:
        res = await self.session.execute(
            select(Promocode).where(Promocode.code == code)
        )
        return res.scalar_one_or_none()
    
    async def get_by_code_for_update(self, code: str) -> Promocode | None:
        res = await self.session.execute(
            select(Promocode)
            .where(Promocode.code == code)
            .with_for_update()
        )
        return res.scalar_one_or_none()
    
    async def ic_activated_by_user(self, promocode_id: int, user_id: int) -> bool:
        res = await self.session.execute(
            select(PromocodeActivation.id)
            .where(
                PromocodeActivation.promocode_id == promocode_id,
                PromocodeActivation.user_id == user_id
            )
        )
        return res.scalar_one_or_none() is not None
    
    async def count_activations(self, promocode_id: int) -> int:
        res = await self.session.execute(
            select(PromocodeActivation.id)
            .where(PromocodeActivation.promocode_id == promocode_id)
        )
        return len(res.scalars().all())
    
    async def create(
            self,
            *,
            code: str,
            amount: int,
            usages: int,
            created_at: datetime
    ) -> Promocode:
        promo = Promocode(
            code=code,
            amount=amount,
            usages=usages,
            created_at=created_at
        )
        self.session.add(promo)
        return promo
    
    async def add_activation(
            self,
            *,
            promocode_id: int,
            user_id: int,
            activated_at: datetime
    ) -> None:
        self.session.add(
            PromocodeActivation(
                promocode_id=promocode_id,
                user_id=user_id,
                activated_at=activated_at
            )
        )

    async def decrement_usages(self, promocode_id: int, by: int = 1) -> None:
        await self.session.execute(
            update(Promocode)
            .where(Promocode.id == promocode_id)
            .values(usages=Promocode.usages - by)
        )

    async def mark_activated(
            self,
            *,
            promocode_id: int,
            activated_at: datetime
    ) -> None:
        await self.session.execute(
            update(Promocode)
            .where(Promocode.id == promocode_id)
            .values(
                is_activated=True,
                activated_at=activated_at
            )
        )