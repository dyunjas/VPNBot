from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.repositories.promocode_repository import PromocodeRepository
from backend.repositories.user_repository import UserRepository
from backend.services.exceptions import (
    UserNotFound, PromocodeNotFound, PromocodeAlreadyUsed, PromocodeExhausted
)

from backend.database.models import Promocode

class PromoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.promo_repo = PromocodeRepository(session)
        self.user_repo = UserRepository(session)

    async def activate_promocode(self, user_id: int, code: str) -> Promocode:
        logger.info("[biz][promo] activate_requested user_id=%s code=%s", user_id, code)

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        promo = await self.promo_repo.get_by_code_for_update(code)
        if not promo:
            raise PromocodeNotFound(f"Promocode not found: {code}")

        already_used = await self.promo_repo.ic_activated_by_user(promo.id, user_id)
        if already_used:
            raise PromocodeAlreadyUsed(f"User already activated promocode: user id {user_id}, code {code}")

        if promo.usages <= 0:
            raise PromocodeExhausted(f"Promocode exhausted: {code}")

        before_balance = int(user.balance or 0)
        user.balance += promo.amount

        await self.promo_repo.add_activation(
            promocode_id=promo.id,
            user_id=user.id,
            activated_at=datetime.now(timezone.utc)
        )

        await self.promo_repo.decrement_usages(promo.id, by=1)

        await self.session.commit()
        logger.info(
            "[biz][promo] activated user_id=%s code=%s amount=%s balance_before=%s balance_after=%s",
            user_id,
            code,
            promo.amount,
            before_balance,
            int(user.balance or 0),
        )
        return promo

    async def create_promocode(self, code: str, amount: int, usages: int):
        promo = await self.promo_repo.create(
            code=code,
            amount=amount,
            usages=usages,
            created_at=datetime.now(timezone.utc)
        )
        await self.session.commit()
        logger.info(
            "[biz][promo] created code=%s amount=%s usages=%s",
            code,
            amount,
            usages,
        )
        return promo

    async def get_promocode(self, code: str):
        promo = await self.promo_repo.get_by_code(code)
        if not promo:
            raise PromocodeNotFound(f"Promocode not found: {code}")
        return promo
