from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Admin


class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Admin | None:
        res = await self.session.execute(
            select(Admin)
            .where(Admin.user_id == user_id)
        )
        return res.scalar_one_or_none()