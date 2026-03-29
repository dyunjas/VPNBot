from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.repositories.referral_repository import ReferralRepository
from backend.repositories.user_repository import UserRepository
from backend.services.subscription_service import SubscriptionService
from backend.services.exceptions import UserNotFound


REF_BONUS_HOURS = 72

class ReferralService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.referral_repo = ReferralRepository(session)
        self.user_repo = UserRepository(session)
        self.sub_service = SubscriptionService(session)

    async def create_account(self, user_id: int):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        account = await self.referral_repo.get_account(user_id)
        if account:
            return account
        
        account = await self.referral_repo.create_account(user_id)
        await self.session.flush()
        logger.info("[biz][referral] account_created user_id=%s account_id=%s", user_id, account.id)
        return account
    
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

        await self.create_account(user_id)
        await self.create_account(referrer_id)

        updated = await self.referral_repo.set_referrer_if_empty(
            user_id=user_id,
            referrer_id=referrer_id
        )

        if updated:
            await self.referral_repo.increase_invited_count(referrer_id)

            await self.sub_service.renew_subscription(
                user_id=referrer_id,
                duration_hours=REF_BONUS_HOURS,
            )

            await self.session.commit()
            logger.info(
                "[biz][referral] referrer_attached user_id=%s referrer_id=%s bonus_hours=%s",
                user_id,
                referrer_id,
                REF_BONUS_HOURS,
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
        
        if not user.referrer_id:
            return 0
        
        referrer_id = user.referrer_id

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
