from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.core.logger_config import logger
from backend.core.business_config import get_business_int
from backend.repositories.referral_repository import ReferralRepository
from backend.repositories.user_repository import UserRepository
from backend.services.remnawave_service import RemnaWaveService
from backend.services.subscription_service import SubscriptionService
from backend.services.exceptions import UserNotFound, BannedUser, NotEnoughReferralBalance


class ReferralService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.referral_repo = ReferralRepository(session)
        self.user_repo = UserRepository(session)
        self.sub_service = SubscriptionService(session)
        self.remnawave_service = RemnaWaveService(session)

    async def create_account(self, user_id: int):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        account = await self.referral_repo.get_account(user_id)
        if account:
            return account

        try:
            account = await self.referral_repo.create_account(user_id)
            await self.session.flush()
            logger.info("[biz][referral] account_created user_id=%s account_id=%s", user_id, account.id)
            return account
        except IntegrityError:
            await self.session.rollback()
            account = await self.referral_repo.get_account(user_id)
            if account:
                return account
            raise
    
    async def get_account(self, user_id: int):
        return await self.referral_repo.get_account(user_id)
    
    async def attach_referrer(self, *, user_id: int, referrer_id: int) -> bool:
        if user_id == referrer_id:
            logger.warning("[biz][referral] attach_self_referrer_blocked user_id=%s", user_id)
            return False

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        referrer_user = await self.user_repo.get_by_id(referrer_id)
        if not referrer_user:
            raise UserNotFound(f"Referrer with id:{referrer_id} not found")
        if bool(getattr(user, "banned", False)):
            logger.warning("[biz][referral] attach_banned_user_blocked user_id=%s referrer_id=%s", user_id, referrer_id)
            raise BannedUser("User is banned")
        if bool(getattr(referrer_user, "banned", False)):
            logger.warning("[biz][referral] attach_banned_referrer_blocked user_id=%s referrer_id=%s", user_id, referrer_id)
            return False

        await self.create_account(user_id)

        updated = await self.referral_repo.set_referrer_if_empty(
            user_id=user_id,
            referrer_id=referrer_id
        )

        if updated:
            await self.referral_repo.increase_invited_count(referrer_id)

            bonus_hours = get_business_int("REFERRAL_BONUS_HOURS")
            sub = await self.sub_service.renew_subscription(
                user_id=referrer_id,
                duration_hours=bonus_hours,
            )

            try:
                await self.remnawave_service.get_subscription_url(
                    user=referrer_user,
                    subscription=sub,
                )
                await self.remnawave_service.sync_user_state(
                    user=referrer_user,
                    subscription=sub,
                    status="ACTIVE",
                )
            except Exception as e:
                logger.exception(
                    "[biz][referral] remnawave_bonus_sync_failed user_id=%s referrer_id=%s subscription_id=%s: %s",
                    user_id,
                    referrer_id,
                    getattr(sub, "id", None),
                    e,
                )

            await self.session.flush()
            logger.info(
                "[biz][referral] referrer_attached user_id=%s referrer_id=%s bonus_hours=%s",
                user_id,
                referrer_id,
                bonus_hours,
            )
            return True

        logger.info(
            "[biz][referral] referrer_attach_skipped user_id=%s referrer_id=%s reason=already_attached",
            user_id,
            referrer_id,
        )
        return False
    
    async def reward_from_purchase(
            self,
            *,
            user_id: int,
            purchase_amount: int
    ) -> int:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        if bool(getattr(user, "banned", False)):
            logger.info("[biz][referral] purchase_reward_skipped user_id=%s reason=payer_banned", user_id)
            return 0
        
        if not user.referrer_id:
            return 0
        
        referrer_id = user.referrer_id

        referrer_user = await self.user_repo.get_by_id(referrer_id)
        if not referrer_user:
            return 0
        if bool(getattr(referrer_user, "banned", False)):
            logger.info(
                "[biz][referral] purchase_reward_skipped user_id=%s referrer_id=%s reason=referrer_banned",
                user_id,
                referrer_id,
            )
            return 0

        ref_account = await self.create_account(referrer_id)
        percent = ref_account.referral_percent

        reward = purchase_amount * percent // 100
        if reward <= 0:
            logger.info(
                "[biz][referral] purchase_reward_zero user_id=%s referrer_id=%s purchase_amount=%s percent=%s",
                user_id,
                referrer_id,
                purchase_amount,
                percent,
            )
            return 0
        
        await self.referral_repo.add_referral_balance(
            user_id=referrer_id,
            amount=reward
        )

        await self.session.commit()
        logger.info(
            "[biz][referral] purchase_reward_added user_id=%s referrer_id=%s purchase_amount=%s percent=%s reward=%s",
            user_id,
            referrer_id,
            purchase_amount,
            percent,
            reward,
        )
        return reward
    
    async def get_balance(self, user_id: int) -> int:
        account = await self.create_account(user_id)
        return account.referral_balance

    async def transfer_to_user_balance(self, *, user_id: int, amount: int) -> dict[str, int]:
        amount = int(amount or 0)
        min_amount = get_business_int("MIN_REFERRAL_TRANSFER_AMOUNT_RUB")
        if amount < min_amount:
            raise ValueError(f"Minimum referral transfer amount is {min_amount} RUB")

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        if bool(getattr(user, "banned", False)):
            raise BannedUser("User is banned")

        account = await self.create_account(user_id)
        updated = await self.referral_repo.decrease_balance_if_enough(
            user_id=user_id,
            amount=amount,
        )
        if not updated:
            logger.info(
                "[biz][referral] transfer_to_balance_insufficient user_id=%s amount=%s referral_balance=%s",
                user_id,
                amount,
                int(account.referral_balance or 0),
            )
            raise NotEnoughReferralBalance("Not enough referral balance")

        await self.user_repo.add_balance(user_id=user_id, amount=amount)
        await self.session.commit()

        fresh_user = await self.user_repo.get_by_id(user_id)
        fresh_account = await self.referral_repo.get_account(user_id)
        logger.info(
            "[biz][referral] transfer_to_balance_completed user_id=%s amount=%s user_balance=%s referral_balance=%s",
            user_id,
            amount,
            int(getattr(fresh_user, "balance", 0) or 0),
            int(getattr(fresh_account, "referral_balance", 0) or 0),
        )
        return {
            "amount": amount,
            "balance": int(getattr(fresh_user, "balance", 0) or 0),
            "referral_balance": int(getattr(fresh_account, "referral_balance", 0) or 0),
        }
