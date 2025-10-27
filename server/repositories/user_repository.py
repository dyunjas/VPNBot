from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from server.database.models import User, Key


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(
            self,
            tg_id: int,
            username: str | None
    ) -> User:
        user = User(
            tg_id=tg_id,
            username=username,
            balance=0
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_user_by_tg_id(self, tg_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()
    
    async def increase_balance(self, tg_id: int, amount: int) -> int:
        user = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user.scalar_one()
        user.balance += amount
        await self.session.commit()
        await self.session.refresh(user)
        return user.balance
    
    async def decrease_balance(self, tg_id: int, amount: int) -> int:
        user = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user.scalar_one()
        user.balance -= amount
        await self.session.commit()
        await self.session.refresh(user)
        return user.balance
    
    async def update_username(self, tg_id: int, new_username: str | None):
        user = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user.scalar_one()
        user.username = new_username
        await self.session.commit()

    async def delete_user_key_by_key_id(self, key_id: int) -> bool:
        result = await self.session.execute(
            select(Key).where(Key.id == key_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            return False
        
        await self.session.execute(
            delete(Key).where(Key.id == key_id)
        )
        await self.session.commit()
        return True