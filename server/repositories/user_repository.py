from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from server.database.models import User, Key, EmailVerification

from datetime import datetime, timedelta

from client.navigation.additional_menu.email.otp_hash import otp_hash



class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(
            self,
            tg_id: int,
            username: str | None
    ) -> User:
        user = User(
            tg_id=tg_id,
            username=username,
            balance=0
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_user_by_tg_id(self, tg_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()
    
    async def increase_balance(self, tg_id: int, amount: int) -> int:
        user = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user.scalar_one()
        user.balance += amount
        await self.session.commit()
        await self.session.refresh(user)
        return user.balance
    
    async def decrease_balance(self, tg_id: int, amount: int) -> int:
        user = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user.scalar_one()
        user.balance -= amount
        await self.session.commit()
        await self.session.refresh(user)
        return user.balance
    
    async def update_username(self, tg_id: int, new_username: str | None):
        user = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user.scalar_one()
        user.username = new_username
        await self.session.commit()

    async def delete_user_key_by_key_id(self, key_id: int) -> bool:
        result = await self.session.execute(
            select(Key).where(Key.id == key_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            return False
        
        await self.session.execute(
            delete(Key).where(Key.id == key_id)
        )
        await self.session.commit()
        return True
    
    async def get_user_email(self, tg_id: int) -> str | None:
        result = await self.session.execute(
            select(User.email).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()

    async def check_email_taken(self, email: str) -> bool:
        email = email.strip().lower()
        result = await self.session.execute(
            select(User.id).where(User.email == email)
        )
        return result.scalar_one_or_none() is not None

    async def set_email_unique(self, tg_id: int, email: str) -> bool:
        email = email.strip().lower()

        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = result.scalar_one()

        user.email = email
        user.updated_at = datetime.now()

        try:
            await self.session.commit()
            return True
        except IntegrityError:
            await self.session.rollback()
            return False


    async def upsert_email_verification(self, tg_id: int, email: str, code: str, ttl_minutes: int = 10) -> None:
        now = datetime.now()
        expires_at = now + timedelta(minutes=ttl_minutes)
        code_hash = otp_hash(code)

        existing = await self.session.execute(
            select(EmailVerification).where(EmailVerification.tg_id == tg_id)
        )
        row = existing.scalar_one_or_none()

        if row:
            row.email = email
            row.code_hash = code_hash
            row.expires_at = expires_at
            row.attempts = 0
            row.last_sent_at = now
        else:
            self.session.add(EmailVerification(
                tg_id=tg_id,
                email=email,
                code_hash=code_hash,
                expires_at=expires_at,
                attempts=0,
                last_sent_at=now
            ))

        await self.session.commit()

    async def get_email_verification(self, tg_id: int) -> EmailVerification | None:
        result = await self.session.execute(
            select(EmailVerification).where(EmailVerification.tg_id == tg_id)
        )
        return result.scalar_one_or_none()

    async def increase_email_verification_attempts(self, tg_id: int) -> None:
        result = await self.session.execute(
            select(EmailVerification).where(EmailVerification.tg_id == tg_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.attempts += 1
            await self.session.commit()

    async def delete_email_verification(self, tg_id: int) -> None:
        await self.session.execute(
            delete(EmailVerification).where(EmailVerification.tg_id == tg_id)
        )
        await self.session.commit()

    async def set_referrer_if_empty(self, user_id: int, referrer_id: int) -> bool:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .where(User.referrer_id.is_(None))
            .values(referrer_id=referrer_id, updated_at=datetime.now())
        )
        res = await self.session.execute(stmt)
        if res.rowcount:
            await self.session.commit()
            return True
        return False
    