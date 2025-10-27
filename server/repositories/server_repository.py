from __future__ import annotations
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.database.models import Server, Key, KeyStatus

class ServerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_servers(self) -> List[Server]:
        result = await self.session.execute(
            select(Server).order_by(Server.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_server_by_id(self, server_id: int) -> Optional[Server]:
        result = await self.session.execute(
            select(Server).where(Server.id == server_id)
        )
        return result.scalar_one_or_none()
    
    async def get_server_info(self, server_id: int) -> Optional[dict]:
        server = await self.get_server_by_id(server_id)
        if not server:
            return None

        q = (
            select(
                func.sum(func.case((Key.status == KeyStatus.active, 1), else_=0)).label("active_cnt"),
                func.count(Key.id).label("total_cnt"),
            )
            .where(Key.server_id == server_id)
        )
        res = await self.session.execute(q)
        row = res.one()
        active_cnt = int(row.active_cnt or 0)
        total_cnt = int(row.total_cnt or 0)

        return {
            "id": server.id,
            "country": server.country,
            "inbound_tag": server.inbound_tag,
            "grpc_endpoint": server.grpc_endpoint,
            "public_host": server.public_host,
            "note": server.note,
            "created_at": server.created_at,
            "active_keys": active_cnt,
            "total_keys": total_cnt,
        }
    
    async def get_servers_with_load(self) -> List[dict]:
        subq = (
            select(
                Key.server_id.label("sid"),
                func.sum(func.case((Key.status == KeyStatus.active, 1), else_=0)).label("active_cnt"),
                func.count(Key.id).label("total_cnt"),
            )
            .group_by(Key.server_id)
            .subquery()
        )

        stmt = (
            select(
                Server,
                func.coalesce(subq.c.active_cnt, 0),
                func.coalesce(subq.c.total_cnt, 0),
            )
            .outerjoin(subq, Server.id == subq.c.sid)
            .order_by(Server.created_at.desc())
        )

        res = await self.session.execute(stmt)
        rows = res.all()

        data: List[dict] = []
        for server, active_cnt, total_cnt in rows:
            data.append({
                "id": server.id,
                "country": server.country,
                "inbound_tag": server.inbound_tag,
                "grpc_endpoint": server.grpc_endpoint,
                "public_host": server.public_host,
                "note": server.note,
                "created_at": server.created_at,
                "active_keys": int(active_cnt),
                "total_keys": int(total_cnt),
            })
        return data
    
    async def get_available_servers(self, max_active_keys_per_server: int) -> List[Server]:

        subq = (
            select(
                Key.server_id.label("sid"),
                func.sum(func.case((Key.status == KeyStatus.active, 1), else_=0)).label("active_cnt"),
            )
            .group_by(Key.server_id)
            .subquery()
        )

        stmt = (
            select(Server)
            .outerjoin(subq, Server.id == subq.c.sid)
            .where(func.coalesce(subq.c.active_cnt, 0) <= max_active_keys_per_server)
            .order_by(Server.created_at.desc())
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()
