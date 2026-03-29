import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.database.models import User
from backend.repositories.user_repository import UserRepository
from backend.services.exceptions import UserNotFound, InsufficientBalance


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def create_user(self, tg_id: int, username: str | None = None):
        user = await self.user_repo.get_by_tg_id(tg_id)
        if not user:
            user = await self.user_repo.create(tg_id=tg_id, username=username)
            self.user_repo.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            logger.info(
                "[biz][user] created user_id=%s tg_id=%s username=%s",
                user.id,
                tg_id,
                username,
            )
        return user

    async def get_by_id(self, user_id: int):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        return user
    
    async def get_by_tg_id(self, tg_id: int):
        user = await self.user_repo.get_by_tg_id(tg_id)
        if not user:
            raise UserNotFound(f"User with id:{tg_id} not found")
        return user
    
    async def get_by_subscription_token(self, token: str):
        user = await self.user_repo.get_user_by_token(token)
        if not user:
            raise UserNotFound("User with given subscription token not found")
        return user

    async def set_username(self, user_id: int, username: str):
        user = await self.user_repo.get_by_id(user_id)
        if not user:   
            raise UserNotFound(f"User with id:{user_id} not found")
        prev_username = user.username
        await self.user_repo.set_username(user_id=user_id, username=username)
        await self.session.commit()
        logger.info(
            "[biz][user] username_updated user_id=%s old=%s new=%s",
            user_id,
            prev_username,
            username,
        )

    async def get_balance(self, user_id: int) -> int:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        return user.balance

    async def add_balance(self, user_id: int, amount: int) -> int:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        before = int(user.balance or 0)
        await self.user_repo.add_balance(user_id=user_id, amount=amount)
        await self.session.commit()
        await self.session.refresh(user)
        logger.info(
            "[biz][user] balance_added user_id=%s amount=%s before=%s after=%s",
            user_id,
            amount,
            before,
            int(user.balance or 0),
        )
        return user.balance

    async def sub_balance(self, user_id: int, amount: int) -> int:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        if user.balance < amount:
            raise InsufficientBalance("Insufficient balance")
        before = int(user.balance or 0)
        await self.user_repo.sub_balance(user_id=user_id, amount=amount)
        await self.session.commit()
        await self.session.refresh(user)
        logger.info(
            "[biz][user] balance_subtracted user_id=%s amount=%s before=%s after=%s",
            user_id,
            amount,
            before,
            int(user.balance or 0),
        )
        return user.balance

    async def get_subscription_token(self, user_id: int) -> str:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        if not user.subscription_token:
            token = str(uuid.uuid4())
            await self.user_repo.set_subscription_token(user_id=user_id, token=token)
            await self.session.commit()
            logger.info("[biz][user] subscription_token_issued user_id=%s", user_id)
            return token
        return user.subscription_token

    async def reissue_subscription_token(self, user_id: int) -> str:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        token = await self.user_repo.reissue_subscription_token(user_id=user_id)
        await self.session.commit()
        logger.info("[biz][user] subscription_token_reissued user_id=%s", user_id)
        return token

    async def set_referrer(
        self,
        *,
        user_id: int,
        referrer_id: int,
        only_id_empty: bool = True,
    ) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        if only_id_empty:
            update_rows = await self.user_repo.set_refferal_if_empty(
                user_id=user_id,
                referrer_id=referrer_id,
            )
            await self.session.commit()
            logger.info(
                "[biz][user] referrer_set_if_empty user_id=%s referrer_id=%s success=%s",
                user_id,
                referrer_id,
                update_rows > 0,
            )
            return update_rows > 0

        await self.user_repo.set_referrer(user_id=user_id, referrer_id=referrer_id)
        await self.session.commit()
        logger.info(
            "[biz][user] referrer_forced user_id=%s referrer_id=%s",
            user_id,
            referrer_id,
        )
        return True
    
    async def get_all_users(self) -> list[User]:
        return await self.user_repo.get_all_users()
        
