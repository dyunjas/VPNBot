from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import UserDevice, Subscription


class DeviceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, device_id: int) -> UserDevice | None:
        res = await self.session.execute(select(UserDevice).where(UserDevice.id == device_id))
        return res.scalar_one_or_none()

    async def get_by_user_and_id(self, user_id: int, device_id: int) -> UserDevice | None:
        res = await self.session.execute(
            select(UserDevice).where(
                UserDevice.user_id == user_id,
                UserDevice.id == device_id,
            )
        )
        return res.scalar_one_or_none()

    async def get_by_user_and_hwid(self, user_id: int, hwid: str) -> UserDevice | None:
        res = await self.session.execute(
            select(UserDevice).where(
                UserDevice.user_id == user_id,
                UserDevice.hwid == hwid
            )
        )
        return res.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> list[UserDevice]:
        res = await self.session.execute(
            select(UserDevice)
            .where(UserDevice.user_id == user_id)
            .order_by(UserDevice.last_seen_at.desc())
        )
        return list(res.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        res = await self.session.execute(
            select(func.count(UserDevice.id)).where(UserDevice.user_id == user_id)
        )
        return int(res.scalar_one() or 0)

    async def create(
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
    ) -> UserDevice:
        seen_at = seen_at or datetime.now(timezone.utc)
        dev = UserDevice(
            user_id=user_id,
            hwid=hwid,
            device_model=device_model,
            device_os=device_os,
            os_version=os_version,
            device_locale=device_locale,
            user_agent=user_agent,
            first_seen_at=seen_at,
            last_seen_at=seen_at,
        )
        self.session.add(dev)
        return dev

    async def touch_last_seen(
        self,
        *,
        user_id: int,
        hwid: str,
        seen_at: datetime | None = None,
    ) -> int:
        seen_at = seen_at or datetime.now(timezone.utc)
        res = await self.session.execute(
            update(UserDevice)
            .where(UserDevice.user_id == user_id, UserDevice.hwid == hwid)
            .values(last_seen_at=seen_at)
        )
        return int(res.rowcount or 0)

    async def update_device_meta_by_hwid(
        self,
        *,
        user_id: int,
        hwid: str,
        device_model: str | None = None,
        device_os: str | None = None,
        os_version: str | None = None,
        device_locale: str | None = None,
        user_agent: str | None = None,
        last_seen_at: datetime | None = None,
    ) -> int:
        values = {}
        if device_model is not None:
            values["device_model"] = device_model
        if device_os is not None:
            values["device_os"] = device_os
        if os_version is not None:
            values["os_version"] = os_version
        if device_locale is not None:
            values["device_locale"] = device_locale
        if user_agent is not None:
            values["user_agent"] = user_agent
        if last_seen_at is not None:
            values["last_seen_at"] = last_seen_at

        if not values:
            return 0

        res = await self.session.execute(
            update(UserDevice)
            .where(UserDevice.user_id == user_id, UserDevice.hwid == hwid)
            .values(**values)
        )
        return int(res.rowcount or 0)

    async def delete_by_user_and_hwid(self, user_id: int, hwid: str) -> int:
        res = await self.session.execute(
            delete(UserDevice).where(
                UserDevice.user_id == user_id,
                UserDevice.hwid == hwid
            )
        )
        return int(res.rowcount or 0)

    async def delete_by_id(self, device_id: int) -> int:
        res = await self.session.execute(
            delete(UserDevice).where(UserDevice.id == device_id)
        )
        return int(res.rowcount or 0)

    async def decrease_device_slot(self, subscription_id: int) -> int:
        res = await self.session.execute(
            update(Subscription)
            .where(
                Subscription.id == subscription_id,
                Subscription.devices_left > 0,
            )
            .values(devices_left=Subscription.devices_left - 1)
        )
        return int(res.rowcount or 0)

    async def increase_device_slot(self, subscription_id: int) -> int:
        res = await self.session.execute(
            update(Subscription)
            .where(
                Subscription.id == subscription_id,
                Subscription.devices_left < Subscription.devices_limit,
            )
            .values(devices_left=Subscription.devices_left + 1)
        )
        return int(res.rowcount or 0)

    async def sync_devices_limit_from_plan(self, subscription_id: int, new_limit: int) -> int:
        res = await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(
                devices_limit=new_limit,
                devices_left=func.least(Subscription.devices_left, new_limit),
            )
        )
        return int(res.rowcount or 0)

    async def get_subscription_slots(self, subscription_id: int) -> Subscription | None:
        return await self.session.get(Subscription, subscription_id)
