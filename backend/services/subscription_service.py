from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.business_config import get_business_int
from backend.core.logger_config import logger
from backend.database.models import SubStatus, Subscription
from backend.repositories.subscription_repository import SubscriptionRepository
from backend.repositories.subscription_topup_repository import SubscriptionTopupRepository
from backend.repositories.user_repository import UserRepository
from backend.services.exceptions import (
    UserNotFound,
    BannedUser,
    SubscriptionNotFound,
    PlanNotFound, TooEarlyToRenew
)
from backend.services.activity_service import ActivityService


class SubscriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sub_repo = SubscriptionRepository(session)
        self.topup_repo = SubscriptionTopupRepository(session)
        self.user_repo = UserRepository(session)
        self.activity_service = ActivityService(session)

    @staticmethod
    def _gb_to_bytes(gb: Decimal) -> int:
        return max(0, int((Decimal(gb or 0) * Decimal(1024**3)).to_integral_value()))

    async def _refresh_user_traffic_limit_snapshot(self, *, user_id: int, subscription) -> int:
        if not subscription:
            await self.user_repo.set_traffic_limit_bytes(user_id=user_id, traffic_limit_bytes=0)
            return 0

        plan = await self.sub_repo.get_plan_by_id(int(subscription.plan_id))
        plan_gb = Decimal(getattr(plan, "gb_limit", 0) or 0)
        topup_gb = await self.topup_repo.sum_gb(subscription_id=subscription.id)
        traffic_limit_bytes = self._gb_to_bytes(plan_gb + Decimal(topup_gb or 0))
        await self.user_repo.set_traffic_limit_bytes(
            user_id=user_id,
            traffic_limit_bytes=traffic_limit_bytes,
        )
        logger.info(
            "[biz][subscription] traffic_limit_snapshot_updated user_id=%s subscription_id=%s traffic_limit_bytes=%s",
            user_id,
            subscription.id,
            traffic_limit_bytes,
        )
        return traffic_limit_bytes

    async def _reset_user_traffic_safe(self, user_id: int) -> None:
        logger.info("[subscription] reset_user_traffic skipped user_id=%s (remnawave-only mode)", user_id)

    async def list_plans(self, *, include_hidden: bool = False):
        plans = list(await self.sub_repo.list_plans(include_hidden=include_hidden))
        if include_hidden:
            return plans

        visible_plans = []
        hidden_changed = False
        for plan in plans:
            if await self._is_plan_exhausted(plan):
                await self._hide_exhausted_plan(plan)
                hidden_changed = True
                continue
            visible_plans.append(plan)
        if hidden_changed:
            await self.session.commit()
        return visible_plans

    async def get_plan(self, plan_id: int):
        plan = await self.sub_repo.get_plan_by_id(plan_id)
        if not plan:
            raise PlanNotFound("Plan not found")
        return plan

    async def get_trial_plan(self):
        plan = await self.sub_repo.get_trial_plan()
        if not plan:
            return None
        if await self._is_plan_exhausted(plan):
            await self._hide_exhausted_plan(plan)
            await self.session.commit()
            return None
        return plan

    async def get_public_plan(self, plan_id: int):
        plan = await self.get_plan(plan_id)
        if bool(getattr(plan, "is_hidden", False)):
            raise PlanNotFound("Plan not found")
        if await self._is_plan_exhausted(plan):
            await self._hide_exhausted_plan(plan)
            await self.session.commit()
            raise PlanNotFound("Plan not found")
        return plan

    async def _is_plan_exhausted(self, plan) -> bool:
        purchase_limit = max(0, int(getattr(plan, "purchase_limit", 0) or 0))
        if purchase_limit <= 0:
            return False
        current_count = await self.sub_repo.count_plan_subscriptions(plan_id=int(plan.id))
        return current_count >= purchase_limit

    async def _hide_exhausted_plan(self, plan) -> None:
        if bool(getattr(plan, "is_hidden", False)):
            return
        plan.is_hidden = True
        await self.session.flush()

    async def get_active_subscription(self, user_id: int):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        sub = await self.sub_repo.get_active_with_plan(
            user_id,
            now=datetime.now(timezone.utc),
        )

        if not sub:
            raise SubscriptionNotFound("Active subscription not found")

        return sub

    @staticmethod
    def _ensure_user_not_banned(user) -> None:
        if bool(getattr(user, "banned", False)):
            raise BannedUser("User is banned")

    async def activate_subscription(
        self,
        user_id: int,
        plan_id: int,
        auto_renew: bool,
    ):
        logger.info(
            "[biz][subscription] activate_requested user_id=%s plan_id=%s auto_renew=%s",
            user_id,
            plan_id,
            auto_renew,
        )
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("[biz][subscription] activate_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")
        self._ensure_user_not_banned(user)

        plan = await self.get_plan(plan_id)
        plan_device_limit = max(0, int(getattr(plan, "device_limit", 0) or 0))

        now = datetime.now(timezone.utc)
        period = timedelta(days=plan.period_days)

        sub = await self.sub_repo.get_by_id_for_update(user_id)

        if sub:
            end = sub.current_period_end

            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if end and end > now:
                time_left = end - now

                renewal_window_days = get_business_int("SUBSCRIPTION_RENEWAL_WINDOW_DAYS")
                if time_left > timedelta(days=renewal_window_days):
                    logger.warning(
                        "[biz][subscription] activate_too_early user_id=%s plan_id=%s seconds_left=%s",
                        user_id,
                        plan_id,
                        int(time_left.total_seconds()),
                    )
                    raise TooEarlyToRenew(
                        f"Subscription can only be renewed within {renewal_window_days} days before expiration"
                    )

        if not sub:
            sub = await self.sub_repo.create(
                user_id=user_id,
                plan_id=plan.id,
                status=SubStatus.active,
                auto_renew=auto_renew,
                device_limit=plan_device_limit,
                current_period_start=now,
                current_period_end=now + period,
                next_renewal_at=now + period,
            )
            await self.session.flush()
            logger.info(
                "[biz][subscription] created user_id=%s subscription_id=%s plan_id=%s period_end=%s gb_added=%s",
                user_id,
                sub.id,
                plan.id,
                sub.current_period_end,
                plan.gb_limit,
            )

        else:
            end = sub.current_period_end
            previous_plan = await self.sub_repo.get_plan_by_id(int(sub.plan_id))
            previous_plan_gb = Decimal(getattr(previous_plan, "gb_limit", 0) or 0) if previous_plan else Decimal(0)

            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if end and end > now:
                start = sub.current_period_start
                end = end + period
            else:
                start = now
                end = now + period

            await self.sub_repo.set_plan_and_period(
                sub,
                plan_id=plan.id,
                status=SubStatus.active,
                auto_renew=auto_renew,
                device_limit=plan_device_limit,
                current_period_start=start,
                current_period_end=end,
                next_renewal_at=end,
            )
            await self.session.flush()
            if previous_plan_gb > 0:
                await self.topup_repo.add_topup(subscription_id=sub.id, gb=previous_plan_gb)
                await self.activity_service.log_user_event(
                    user_id=user_id,
                    category="traffic",
                    action="traffic_added",
                    source="system",
                    traffic_gb=previous_plan_gb,
                    subscription_id=sub.id,
                    note="Начисление трафика за продление подписки",
                )
            logger.info(
                "[biz][subscription] renewed user_id=%s subscription_id=%s plan_id=%s period_end=%s gb_limit=%s rollover_gb=%s",
                user_id,
                sub.id,
                plan.id,
                end,
                plan.gb_limit,
                previous_plan_gb,
            )

        await self._reset_user_traffic_safe(user_id=user_id)
        await self._refresh_user_traffic_limit_snapshot(user_id=user_id, subscription=sub)
        await self.activity_service.log_user_event(
            user_id=user_id,
            category="subscription",
            action="subscription_activated",
            source="system",
            subscription_id=sub.id,
            note=f"План {plan.id}, период {plan.period_days} дн., трафик {plan.gb_limit} GB",
        )
        if await self._is_plan_exhausted(plan):
            await self._hide_exhausted_plan(plan)
        await self.session.commit()
        logger.info(
            "[biz][subscription] activate_completed user_id=%s subscription_id=%s",
            user_id,
            sub.id,
        )
        return sub
    
    async def renew_subscription(
        self, 
        *,
        user_id: int,
        duration_hours: int
    ):
        logger.info(
            "[biz][subscription] renew_requested user_id=%s duration_hours=%s",
            user_id,
            duration_hours,
        )
        if duration_hours <= 0:
            raise ValueError("Duration hours must be > 0")
        
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("[biz][subscription] renew_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")
        self._ensure_user_not_banned(user)
        
        now = datetime.now(timezone.utc)
        delta = timedelta(hours=duration_hours)

        sub = await self.sub_repo.get_by_id_for_update(user_id)

        if not sub:
            default_plan = await self.sub_repo.get_plan_by_id(1)
            if not default_plan:
                logger.error("[biz][subscription] renew_default_plan_missing user_id=%s", user_id)
                raise PlanNotFound("Default plan not found")
            
            sub = await self.sub_repo.create(
                user_id=user_id,
                plan_id=default_plan.id,
                status=SubStatus.active,
                auto_renew=False,
                device_limit=max(0, int(getattr(default_plan, "device_limit", 0) or 0)),
                current_period_start=now,
                current_period_end=now + delta,
                next_renewal_at=now + delta
            )
            await self.session.flush()
            logger.info(
                "[biz][subscription] renew_created_default user_id=%s subscription_id=%s period_end=%s gb_added=%s",
                user_id,
                sub.id,
                sub.current_period_end,
                default_plan.gb_limit,
            )
        
        else:
            end = sub.current_period_end

            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if end and end > now:
                start = sub.current_period_start
                new_end = end + delta
            else:
                start = now
                new_end = now + delta
            
            await self.sub_repo.set_plan_and_period(
                sub,
                plan_id=sub.plan_id,
                status=SubStatus.active,
                auto_renew=sub.auto_renew,
                device_limit=max(0, int(getattr(sub, "device_limit", 0) or 0)),
                current_period_start=start,
                current_period_end=new_end,
                next_renewal_at=new_end,
            )
            await self.session.flush()
            logger.info(
                "[biz][subscription] renew_extended user_id=%s subscription_id=%s new_period_end=%s",
                user_id,
                sub.id,
                new_end,
            )
        
        await self._reset_user_traffic_safe(user_id=user_id)
        await self._refresh_user_traffic_limit_snapshot(user_id=user_id, subscription=sub)
        await self.activity_service.log_user_event(
            user_id=user_id,
            category="subscription",
            action="subscription_renewed",
            source="system",
            subscription_id=sub.id,
            note=f"Продление на {duration_hours} ч.",
        )
        await self.session.commit()
        logger.info(
            "[biz][subscription] renew_completed user_id=%s subscription_id=%s",
            user_id,
            sub.id,
        )
        return sub

    async def add_traffic(self, user_id: int, gb: Decimal):
        logger.info(
            "[biz][subscription] add_traffic_requested user_id=%s gb=%s",
            user_id,
            gb,
        )
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("[biz][subscription] add_traffic_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")
        self._ensure_user_not_banned(user)
        sub = await self.get_active_subscription(user_id)
        if not sub:
            logger.warning("[biz][subscription] add_traffic_sub_not_found user_id=%s", user_id)
            raise SubscriptionNotFound("Subscription not found")

        await self.topup_repo.add_topup(subscription_id=sub.id, gb=gb)
        await self._refresh_user_traffic_limit_snapshot(user_id=user_id, subscription=sub)
        await self.activity_service.log_user_event(
            user_id=user_id,
            category="traffic",
            action="traffic_added",
            source="system",
            traffic_gb=gb,
            subscription_id=sub.id,
            note="Выдача дополнительного трафика",
        )
        logger.info(
            "[biz][subscription] add_traffic_completed user_id=%s subscription_id=%s gb=%s",
            user_id,
            sub.id,
            gb,
        )
        return sub

    async def get_topup_gb(self, subscription_id: int) -> Decimal:
        return await self.topup_repo.sum_gb(subscription_id=subscription_id)
    
    async def list_active_expired(self, *, now: datetime):
        return await self.sub_repo.list_active_expired(now=now)

    async def list_active_ending_between(self, *, start: datetime, end: datetime):
        return await self.sub_repo.list_active_ending_between(start=start, end=end)

    async def mark_expired(self, *, subscription_id: int) -> None:
        sub = await self.session.get(Subscription, subscription_id)
        if not sub:
            logger.warning(
                "[biz][subscription] mark_expired_not_found subscription_id=%s",
                subscription_id,
            )
            raise SubscriptionNotFound("Subscription not found")
        updated = await self.sub_repo.mark_expired(subscription_id=subscription_id)
        if updated <= 0:
            logger.warning(
                "[biz][subscription] mark_expired_not_found subscription_id=%s",
                subscription_id,
            )
            raise SubscriptionNotFound("Subscription not found")
        await self.activity_service.log_user_event(
            user_id=sub.user_id,
            category="subscription",
            action="subscription_expired",
            source="system",
            subscription_id=sub.id,
            note="Подписка переведена в expired",
        )
        await self.session.commit()
        logger.info(
            "[biz][subscription] marked_expired subscription_id=%s",
            subscription_id,
        )

    async def set_auto_renew(
        self,
        *,
        user_id: int,
        auto_renew: bool,
    ):
        sub = await self.get_active_subscription(user_id=user_id)
        updated = await self.sub_repo.set_auto_renew(
            subscription_id=sub.id,
            auto_renew=auto_renew,
        )
        if updated <= 0:
            logger.warning(
                "[biz][subscription] set_auto_renew_not_found user_id=%s auto_renew=%s",
                user_id,
                auto_renew,
            )
            raise SubscriptionNotFound("Subscription not found")
        sub.auto_renew = auto_renew
        await self.activity_service.log_user_event(
            user_id=user_id,
            category="subscription",
            action="auto_renew_changed",
            source="system",
            subscription_id=sub.id,
            note=f"auto_renew={auto_renew}",
        )
        await self.session.commit()
        logger.info(
            "[biz][subscription] auto_renew_changed user_id=%s subscription_id=%s auto_renew=%s",
            user_id,
            sub.id,
            auto_renew,
        )
        return sub
    
    
