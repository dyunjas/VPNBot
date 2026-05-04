from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class DeviceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, device_id: int):
        return None

    async def get_by_user_and_id(self, user_id: int, device_id: int):
        return None

    async def get_by_user_and_hwid(self, user_id: int, hwid: str):
        return None

    async def list_by_user(self, user_id: int) -> list:
        return []

    async def count_by_user(self, user_id: int) -> int:
        return 0

    async def create(self, **kwargs):
        return None

    async def touch_last_seen(self, **kwargs) -> int:
        return 0

    async def update_device_meta_by_hwid(self, **kwargs) -> int:
        return 0

    async def delete_by_user_and_hwid(self, user_id: int, hwid: str) -> int:
        return 0

    async def delete_by_id(self, device_id: int) -> int:
        return 0

    async def delete_all_by_user(self, user_id: int) -> int:
        return 0

    async def list_all_paginated(self, *, size: int, offset: int) -> tuple[list, int]:
        return [], 0
