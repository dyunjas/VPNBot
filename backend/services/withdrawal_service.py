from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.database.models import WithdrawalStatus
from backend.repositories.referral_repository import ReferralRepository
from backend.repositories.withdrawal_repository import WithdrawalRepository
from backend.repositories.admin_repository import AdminRepository

from backend.services.exceptions import (
    NotEnoughReferralBalance,
    WithdrawalNotPending,
    WithdrawalNotFound,
    UserNotFound,
    AdminPermissionDenied,
)


class WithdrawalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.referral_repo = ReferralRepository(session)
        self.withdrawal_repo = WithdrawalRepository(session)
        self.admin_repo = AdminRepository(session)

    async def _ensure_admin(self, admin_user_id: int) -> None:
        admin = await self.admin_repo.get_by_id(admin_user_id)
        if not admin or not admin.is_active:
            raise AdminPermissionDenied("Admin permissions required")

    async def get_by_id(
        self,
        *,
        admin_user_id: int,
        withdrawal_id: int
    ):
        await self._ensure_admin(admin_user_id)

        withdrawal = await self.withdrawal_repo.get_by_id(withdrawal_id)
        if not withdrawal:
            raise WithdrawalNotFound(f"Withdrawal id:{withdrawal_id} not found")

        return withdrawal

    async def create_withdrawal(
        self,
        *,
        user_id: int,
        amount: int,
        method: str
    ):
        logger.info(
            "[biz][withdrawal] create_requested user_id=%s amount=%s method=%s",
            user_id,
            amount,
            method,
        )
        if amount <= 0:
            raise ValueError("Amount must be > 0")

        account = await self.referral_repo.get_account(user_id)
        if not account:
            raise UserNotFound(f"Referral account for user_id:{user_id} not found")

        updated = await self.referral_repo.decrease_balance_if_enough(
            user_id=user_id,
            amount=amount
        )
        if not updated:
            logger.warning(
                "[biz][withdrawal] create_insufficient_ref_balance user_id=%s amount=%s",
                user_id,
                amount,
            )
            raise NotEnoughReferralBalance("Not enough referral balance")

        withdrawal = await self.withdrawal_repo.create_withdrawal(
            referral_account_id=account.id,
            amount=amount,
            method=method
        )

        await self.session.commit()
        logger.info(
            "[biz][withdrawal] created user_id=%s withdrawal_id=%s amount=%s method=%s",
            user_id,
            withdrawal.id,
            amount,
            method,
        )
        return withdrawal

    async def list_by_user(self, *, user_id: int, limit: int = 30):
        return await self.withdrawal_repo.list_by_user_id(user_id=user_id, limit=limit)

    async def list_pending(
        self,
        *,
        admin_user_id: int,
        limit: int = 100
    ):
        await self._ensure_admin(admin_user_id)
        return await self.withdrawal_repo.list_pending(limit=limit)

    async def approve(
        self,
        *,
        admin_user_id: int,
        withdrawal_id: int
    ):
        logger.info(
            "[biz][withdrawal] approve_requested admin_user_id=%s withdrawal_id=%s",
            admin_user_id,
            withdrawal_id,
        )
        await self._ensure_admin(admin_user_id)

        withdrawal = await self.withdrawal_repo.get_by_id(withdrawal_id)
        if not withdrawal:
            raise WithdrawalNotFound(f"Withdrawal id:{withdrawal_id} not found")

        updated = await self.withdrawal_repo.set_status_if_pending(
            withdrawal_id=withdrawal_id,
            status=WithdrawalStatus.approved
        )
        if not updated:
            logger.warning(
                "[biz][withdrawal] approve_not_pending admin_user_id=%s withdrawal_id=%s",
                admin_user_id,
                withdrawal_id,
            )
            raise WithdrawalNotPending("Withdrawal is not pending")

        await self.session.commit()

        withdrawal.status = WithdrawalStatus.approved
        logger.info(
            "[biz][withdrawal] approved admin_user_id=%s withdrawal_id=%s",
            admin_user_id,
            withdrawal_id,
        )
        return withdrawal

    async def reject(
        self,
        *,
        admin_user_id: int,
        withdrawal_id: int
    ):
        logger.info(
            "[biz][withdrawal] reject_requested admin_user_id=%s withdrawal_id=%s",
            admin_user_id,
            withdrawal_id,
        )
        await self._ensure_admin(admin_user_id)

        withdrawal = await self.withdrawal_repo.get_by_id(withdrawal_id)
        if not withdrawal:
            raise WithdrawalNotFound(f"Withdrawal id:{withdrawal_id} not found")

        updated = await self.withdrawal_repo.set_status_if_pending(
            withdrawal_id=withdrawal_id,
            status=WithdrawalStatus.rejected
        )
        if not updated:
            logger.warning(
                "[biz][withdrawal] reject_not_pending admin_user_id=%s withdrawal_id=%s",
                admin_user_id,
                withdrawal_id,
            )
            raise WithdrawalNotPending("Withdrawal is not pending")

        account = withdrawal.referral_account
        if not account:
            raise UserNotFound("Referral account not found for withdrawal")

        await self.referral_repo.add_referral_balance(
            user_id=account.user_id,
            amount=withdrawal.amount
        )

        await self.session.commit()

        withdrawal.status = WithdrawalStatus.rejected
        logger.info(
            "[biz][withdrawal] rejected admin_user_id=%s withdrawal_id=%s refund_user_id=%s amount=%s",
            admin_user_id,
            withdrawal_id,
            account.user_id,
            withdrawal.amount,
        )
        return withdrawal
