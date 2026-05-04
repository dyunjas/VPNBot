from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.database.models import Subscription

from datetime import datetime


class DeviceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_active_subscription_with_plan(self, user_id: int) -> Subscription | None:
        return None

    async def get_device_by_hwid(self, *, user_id: int, hwid: str):
        return None

    async def get_device_by_id(self, *, user_id: int, device_id: int):
        return None

    async def list_devices(self, user_id: int) -> list:
        return []

    async def count_devices(self, user_id: int) -> int:
        return 0

    async def get_subscription_with_slots(self, user_id: int) -> Subscription | None:
        return None

    async def register_device_if_new(
        self,
        *,
        user_id: int,
        hwid: str,
        device_model: str | None = None,
        device_os: str | None = None,
        os_version: str | None = None,
        device_locale: str | None = None,
        user_agent: str | None = None,
        seen_at: datetime | None = None,
    ) -> tuple[bool, Subscription | None]:
        logger.info(
            "[biz][device] register_device_if_new skipped user_id=%s hwid=%s (api-only devices mode)",
            user_id,
            hwid.strip(),
        )
        return False, None

    async def delete_device_by_hwid(
        self,
        *,
        user_id: int,
        hwid: str,
        refund_slot: bool = True,
    ) -> Subscription | None:
        logger.info(
            "[biz][device] delete_device_by_hwid skipped user_id=%s hwid=%s (api-only devices mode)",
            user_id,
            hwid.strip(),
        )
        return None

    async def delete_device_by_id(
        self,
        *,
        user_id: int,
        device_id: int,
        refund_slot: bool = True,
    ) -> Subscription | None:
        logger.info(
            "[biz][device] delete_device_by_id skipped user_id=%s device_id=%s (api-only devices mode)",
            user_id,
            device_id,
        )
        return None

    async def remove_device_for_user(self, *, user_id: int, device_id: int) -> None:
        await self.delete_device_by_id(user_id=user_id, device_id=device_id, refund_slot=False)
