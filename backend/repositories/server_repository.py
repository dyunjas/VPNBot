from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Server, Key, KeyStatus


class ServerRepository: 
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[Server]:
        res = await self.session.execute(
            select(Server).order_by(Server.display_order.asc(), Server.id.asc())
        )
        return res.scalars().all()
    
    async def get_by_id(self, server_id: int) -> Optional[Server]:
        res = await self.session.execute(
            select(Server).where(Server.id == server_id)
        )
        return res.scalar_one_or_none()
    
    async def get_load_by_server_id(self, server_id: int) -> tuple[int, int]:
        stmt = (
            select(
                func.sum(case((Key.status == KeyStatus.active, 1), else_=0)).label("active_cnt"),
                func.count(Key.id).label("total_cnt"),
            )
            .where(Key.server_id == server_id)
        )
        res = await self.session.execute(stmt)
        row = res.one()
        active_cnt = int(row.active_cnt or 0)
        total_cnt = int(row.total_cnt or 0)
        return active_cnt, total_cnt

    async def list_with_load(self) -> List[Tuple[Server, int, int]]:
        subq = (
            select(
                Key.server_id.label("sid"),
                func.sum(case((Key.status == KeyStatus.active, 1), else_=0)).label("active_cnt"),
                func.count(Key.id).label("total_cnt"),
            )
            .group_by(Key.server_id)
            .subquery()
        )

        stmt = (
            select(
                Server,
                func.coalesce(subq.c.active_cnt, 0).label("active_cnt"),
                func.coalesce(subq.c.total_cnt, 0).label("total_cnt"),
            )
            .outerjoin(subq, Server.id == subq.c.sid)
            .order_by(Server.display_order.asc(), Server.id.asc())
        )

        res = await self.session.execute(stmt)
        rows = res.all()

        out: List[Tuple[Server, int, int]] = []
        for server, active_cnt, total_cnt in rows:
            out.append((server, int(active_cnt), int(total_cnt)))
        return out
