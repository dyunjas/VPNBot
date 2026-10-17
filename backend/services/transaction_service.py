from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import get_logger
from backend.repositories.transaction_repository import TransactionRepository
from backend.repositories.user_repository import UserRepository
from backend.services.exceptions import TransactionNotFound, UserNotFound
from backend.database.models import Transaction

logger = get_logger("transactions")


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tx_repo = TransactionRepository(session)
        self.user_repo = UserRepository(session)

    async def get_by_id_for_user(self, tx_id: int, user_id: int) -> Transaction:
        tx = await self.tx_repo.get_by_id(tx_id)
        if not tx or tx.user_id != user_id:
            raise TransactionNotFound("Transaction not found")

        return tx

    async def get_by_provider_id(self, provider_transaction_id: str):
        tx = await self.tx_repo.get_by_provider_id(provider_transaction_id)
        if not tx:
            raise TransactionNotFound("Transaction not found")
        return tx

    async def list_by_user(self, user_id: int, *, limit: int | None = None):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        return await self.tx_repo.list_by_user_id(user_id,limit=limit)

    async def mark_paid(self, provider_transaction_id: str):
        logger.info(
            "[biz][transaction] mark_paid_requested provider_id=%s",
            provider_transaction_id,
        )
        tx = await self.get_by_provider_id(provider_transaction_id)
        if not tx.paid:
            tx.paid = True
            tx.paid_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(tx)
            logger.info(
                "[biz][transaction] marked_paid provider_id=%s tx_id=%s user_id=%s amount=%s",
                provider_transaction_id,
                tx.id,
                tx.user_id,
                tx.amount,
            )
        else:
            logger.info(
                "[biz][transaction] mark_paid_skipped_already_paid provider_id=%s tx_id=%s",
                provider_transaction_id,
                tx.id,
            )
        return tx
    
    async def get_last_unpaid_by_system(self, user_id: int, payment_system: str):
        txs = await self.tx_repo.list_by_user_id(user_id)

        ps = (payment_system or "").lower().strip()
        candidates = [t for t in txs if (not t.paid) and (str(t.payment_system).lower().strip() == ps)]

        def _sort_key(tx: Transaction) -> float:
            dt = tx.created_at
            if dt is None:
                return 0.0
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()

        candidates.sort(key=_sort_key, reverse=True)
        return candidates[0] if candidates else None

    async def list_recent_unpaid(
        self,
        user_id: int,
        *,
        limit: int = 3,
        payment_systems: set[str] | None = None,
    ) -> list[Transaction]:
        txs = await self.tx_repo.list_by_user_id(user_id)

        normalized_systems = None
        if payment_systems:
            normalized_systems = {
                str(payment_system).lower().strip()
                for payment_system in payment_systems
                if str(payment_system or "").strip()
            }

        candidates = [
            tx
            for tx in txs
            if (not tx.paid)
            and (
                normalized_systems is None
                or str(tx.payment_system).lower().strip() in normalized_systems
            )
        ]

        def _sort_key(tx: Transaction) -> float:
            dt = tx.created_at
            if dt is None:
                return 0.0
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()

        candidates.sort(key=_sort_key, reverse=True)
        return candidates[: max(1, int(limit or 1))]
