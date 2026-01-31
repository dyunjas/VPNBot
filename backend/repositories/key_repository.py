from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import Key, KeyStatus


class KeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
            self, 
            key_id: int, 
            *, 
            with_server: bool = True
    ) -> Key | None:
        stmt = select(Key).where(Key.id == key_id)
        if with_server:
            stmt = stmt.options(selectinload(Key.server))
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
    
    async def list_by_user_id(
            self,
            user_id: int,
            *,
            with_server: bool = True
    ) -> list[Key]:
        stmt = select(Key).where(Key.user_id == user_id)
        if with_server:
            stmt = stmt.options(selectinload(Key.server))
        res = await self.session.execute(stmt)
        return res.scalars().all()
    
    async def list_active(self) -> list[Key]:
        res = await self.session.execute(select(Key).where(Key.status == KeyStatus.active))
        return res.scalars().all()
    
    async def count_active_by_user(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Key).where(
            Key.user_id == user_id,
            Key.status == KeyStatus.active
        )
        res = await self.session.execute(stmt)
        return int(res.scalar() or 0)
    
    async def get_user_key_on_server(
            self,
            *,
            user_id: int,
            server_id: int,
            statuses: list[KeyStatus],
            with_server: bool = False
    ) -> Key | None:
        stmt = (
            select(Key)
            .where(
                Key.user_id == user_id,
                Key.server_id == server_id,
                Key.status.in_(statuses)
            )
            .limit(1)
        )
        if with_server:
            stmt = stmt.options(selectinload(Key.server))
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
    
    async def list_user_keys_by_status(
        self,
        *,
        user_id: int,
        statuses: list[KeyStatus],
        with_server: bool = True,
    ) -> list[Key]:
        stmt = select(Key).where(Key.user_id == user_id, Key.status.in_(statuses))
        if with_server:
            stmt = stmt.options(selectinload(Key.server))
        res = await self.session.execute(stmt)
        return res.scalars().all()
    
    async def create(
        self,
        *,
        user_id: int,
        server_id: int,
        uuid: str,
        uri: str,
        status: KeyStatus = KeyStatus.active,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> Key:
        key = Key(
            user_id=user_id,
            server_id=server_id,
            uuid=uuid,
            uri=uri,
            status=status,
            created_at=created_at,
            expires_at=expires_at,
        )
        self.session.add(key)
        return key
    
    async def delete_by_id(self, key_id: int) -> int:
        res = await self.session.execute(delete(Key).where(Key.id == key_id))
        return int(res.rowcount or 0)
    
    async def delete_by_user_id(
            self,
            user_id: int,
            *,
            statuses: list[KeyStatus] | None = None
    ) -> int:
        stmt = delete(Key).where(Key.user_id == user_id)
        if statuses:
            stmt = stmt.where(Key.status.in_(statuses))
        res = await self.session.execute(stmt)
        return int(res.rowcount or 0)
    
    async def delete_all_by_user_id(self, user_id: int) -> int:
        res = await self.session.execute(
            delete(Key)
            .where(Key.user_id == user_id)
        )
        return int(res.rowcount or 0)
    
    async def set_status(self, key_id: int, status: KeyStatus) -> int:
        res = await self.session.execute(
            update(Key)
            .where(Key.id == key_id)
            .values(status=status)
        )
        return int(res.rowcount or 0)
    
    async def set_expires_at(self, key_id: int, expires_at: datetime | None) -> int:
        res = await self.session.execute(
            update(Key)
            .where(Key.id == key_id)
            .values(expires_at=expires_at)
        )
        return int(res.rowcount or 0)
    
    async def deactivate_expired(self, now: datetime) -> int:
        res = await self.session.execute(
            update(Key)
            .where(
                Key.status == KeyStatus.active,
                Key.expires_at.is_not(None),
                Key.expires_at < now
            )
            .values(status=KeyStatus.deleted)
        )
        return int(res.rowcount or 0)
