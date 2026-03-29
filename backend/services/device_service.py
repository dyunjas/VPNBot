from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.database.models import UserDevice, Subscription
from backend.repositories.device_repository import DeviceRepository
from backend.repositories.subscription_repository import SubscriptionRepository
from backend.services.exceptions import (
    DeviceNotFound,
    DeviceLimitReached,
    SubscriptionNotFound,
)


class DeviceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.device_repo = DeviceRepository(session)
        self.sub_repo = SubscriptionRepository(session)

    async def _get_active_subscription_with_plan(self, user_id: int) -> Subscription:
        now = datetime.now(timezone.utc)
        sub = await self.sub_repo.get_active_with_plan(user_id=user_id, now=now)
        if not sub:
            raise SubscriptionNotFound("Active subscription not found")
        return sub

    async def _sync_subscription_limit_from_plan(self, sub: Subscription) -> None:
        if sub.plan and sub.devices_limit != int(sub.plan.device_limit):
            await self.device_repo.sync_devices_limit_from_plan(
                subscription_id=sub.id,
                new_limit=int(sub.plan.device_limit),
            )

    async def get_device_by_hwid(self, *, user_id: int, hwid: str) -> UserDevice:
        dev = await self.device_repo.get_by_user_and_hwid(user_id, hwid.strip())
        if not dev:
            raise DeviceNotFound("Device not found")
        return dev

    async def get_device_by_id(self, *, user_id: int, device_id: int) -> UserDevice:
        dev = await self.device_repo.get_by_user_and_id(user_id=user_id, device_id=device_id)
        if not dev:
            raise DeviceNotFound("Device not found")
        return dev

    async def list_devices(self, user_id: int) -> list[UserDevice]:
        return await self.device_repo.list_by_user(user_id)

    async def count_devices(self, user_id: int) -> int:
        return await self.device_repo.count_by_user(user_id)

    async def get_subscription_with_slots(self, user_id: int) -> Subscription:
        sub = await self._get_active_subscription_with_plan(user_id)
        await self._sync_subscription_limit_from_plan(sub)
        await self.session.commit()
        await self.session.refresh(sub)
        return sub

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
        hwid = hwid.strip()
        seen_at = seen_at or datetime.now(timezone.utc)

        existing = await self.device_repo.get_by_user_and_hwid(user_id, hwid)
        if existing:
            await self.device_repo.touch_last_seen(user_id=user_id, hwid=hwid, seen_at=seen_at)
            await self.session.commit()
            logger.info(
                "[biz][device] seen_existing user_id=%s device_id=%s hwid=%s",
                user_id,
                existing.id,
                hwid,
            )
            return False, None

        sub = await self._get_active_subscription_with_plan(user_id)
        await self._sync_subscription_limit_from_plan(sub)

        consumed = await self.device_repo.decrease_device_slot(sub.id)
        if consumed <= 0:
            await self.session.commit()
            logger.warning(
                "[biz][device] register_limit_reached user_id=%s subscription_id=%s hwid=%s",
                user_id,
                sub.id,
                hwid,
            )
            raise DeviceLimitReached("No free device slots")

        await self.device_repo.create(
            user_id=user_id,
            hwid=hwid,
            device_model=device_model,
            device_os=device_os,
            os_version=os_version,
            device_locale=device_locale,
            user_agent=user_agent,
            seen_at=seen_at,
        )

        await self.session.commit()
        await self.session.refresh(sub)
        logger.info(
            "[biz][device] registered user_id=%s subscription_id=%s hwid=%s",
            user_id,
            sub.id,
            hwid,
        )
        return True, sub

    async def delete_device_by_hwid(
        self,
        *,
        user_id: int,
        hwid: str,
        refund_slot: bool = True,
    ) -> Subscription | None:
        hwid = hwid.strip()

        deleted = await self.device_repo.delete_by_user_and_hwid(user_id, hwid)
        if deleted <= 0:
            raise DeviceNotFound("Device not found")

        if not refund_slot:
            await self.session.commit()
            logger.info("[biz][device] deleted_no_refund user_id=%s hwid=%s", user_id, hwid)
            return None

        sub = await self._get_active_subscription_with_plan(user_id)
        await self._sync_subscription_limit_from_plan(sub)

        await self.device_repo.increase_device_slot(sub.id)

        await self.session.commit()
        await self.session.refresh(sub)
        logger.info(
            "[biz][device] deleted_with_refund user_id=%s subscription_id=%s hwid=%s",
            user_id,
            sub.id,
            hwid,
        )
        return sub

    async def delete_device_by_id(
        self,
        *,
        user_id: int,
        device_id: int,
        refund_slot: bool = True,
    ) -> Subscription | None:
        dev = await self.device_repo.get_by_id(device_id)
        if not dev or dev.user_id != user_id:
            raise DeviceNotFound("Device not found")

        deleted = await self.device_repo.delete_by_id(device_id)
        if deleted <= 0:
            raise DeviceNotFound("Device not found")

        if not refund_slot:
            await self.session.commit()
            logger.info(
                "[biz][device] deleted_by_id_no_refund user_id=%s device_id=%s",
                user_id,
                device_id,
            )
            return None

        sub = await self._get_active_subscription_with_plan(user_id)
        await self._sync_subscription_limit_from_plan(sub)

        await self.device_repo.increase_device_slot(sub.id)

        await self.session.commit()
        await self.session.refresh(sub)
        logger.info(
            "[biz][device] deleted_by_id_with_refund user_id=%s subscription_id=%s device_id=%s",
            user_id,
            sub.id,
            device_id,
        )
        return sub

    async def remove_device_for_user(self, *, user_id: int, device_id: int) -> None:
        """Delete device and refund slot when an active subscription exists."""
        try:
            await self.delete_device_by_id(user_id=user_id, device_id=device_id, refund_slot=True)
        except SubscriptionNotFound:
            await self.delete_device_by_id(user_id=user_id, device_id=device_id, refund_slot=False)
