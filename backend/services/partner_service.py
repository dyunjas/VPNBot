import re
import uuid

from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.database.models import PartnerAttribution, PartnerLink, Transaction, User


PARTNER_CODE_RE = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")


class PartnerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def normalize_code(code: str | None = None) -> str:
        raw = (code or "").strip()
        if not raw:
            raw = uuid.uuid4().hex[:10]
        normalized = raw.lower()
        if not PARTNER_CODE_RE.fullmatch(normalized):
            raise ValueError("partner code must be 3-64 chars: letters, digits, _ or -")
        return normalized

    @staticmethod
    def build_url(code: str) -> str:
        bot_username = (getattr(settings, "BOT_USERNAME", None) or "LunetVpnBot").lstrip("@")
        return f"https://t.me/{bot_username}?start=partner_{code}"

    async def create_link(self, *, name: str, code: str | None = None) -> PartnerLink:
        title = (name or "").strip()
        if not title:
            raise ValueError("partner name is required")
        link = PartnerLink(name=title[:128], code=self.normalize_code(code), is_active=True)
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        logger.info("[biz][partner] link_created id=%s code=%s name=%s", link.id, link.code, link.name)
        return link

    async def get_link_by_code(self, code: str, *, active_only: bool = True) -> PartnerLink | None:
        normalized = self.normalize_code(code)
        stmt = select(PartnerLink).where(PartnerLink.code == normalized)
        if active_only:
            stmt = stmt.where(PartnerLink.is_active.is_(True))
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def attach_user(self, *, user_id: int, code: str) -> Literal["attached", "inactive", "not_found", "already_attributed"]:
        link = await self.get_link_by_code(code, active_only=False)
        if not link:
            logger.info("[biz][partner] attach_skipped user_id=%s code=%s reason=link_not_found", user_id, code)
            return "not_found"

        if not link.is_active:
            logger.info("[biz][partner] attach_skipped user_id=%s code=%s reason=inactive", user_id, code)
            return "inactive"

        existing = await self.session.scalar(
            select(PartnerAttribution.id).where(PartnerAttribution.user_id == user_id).limit(1)
        )
        if existing:
            logger.info("[biz][partner] attach_skipped user_id=%s code=%s reason=already_attributed", user_id, code)
            return "already_attributed"

        self.session.add(PartnerAttribution(partner_link_id=link.id, user_id=user_id))
        await self.session.commit()
        logger.info("[biz][partner] user_attached user_id=%s partner_link_id=%s code=%s", user_id, link.id, link.code)
        return "attached"

    async def set_active(self, *, link_id: int, is_active: bool) -> int:
        res = await self.session.execute(
            update(PartnerLink)
            .where(PartnerLink.id == link_id)
            .values(is_active=is_active)
        )
        await self.session.commit()
        return int(res.rowcount or 0)

    async def list_links_with_stats(self, *, search: str | None = None) -> list[dict]:
        new_users_sq = (
            select(
                PartnerAttribution.partner_link_id.label("partner_link_id"),
                func.count(PartnerAttribution.user_id).label("new_users"),
            )
            .group_by(PartnerAttribution.partner_link_id)
            .subquery()
        )
        payments_sq = (
            select(
                PartnerAttribution.partner_link_id.label("partner_link_id"),
                func.count(Transaction.id).label("paid_topups"),
                func.coalesce(func.sum(Transaction.amount), 0).label("paid_amount"),
            )
            .join(Transaction, Transaction.user_id == PartnerAttribution.user_id)
            .where(Transaction.paid.is_(True))
            .group_by(PartnerAttribution.partner_link_id)
            .subquery()
        )

        stmt = (
            select(
                PartnerLink,
                func.coalesce(new_users_sq.c.new_users, 0),
                func.coalesce(payments_sq.c.paid_topups, 0),
                func.coalesce(payments_sq.c.paid_amount, 0),
            )
            .outerjoin(new_users_sq, new_users_sq.c.partner_link_id == PartnerLink.id)
            .outerjoin(payments_sq, payments_sq.c.partner_link_id == PartnerLink.id)
            .order_by(PartnerLink.created_at.desc())
        )

        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            stmt = stmt.where(
                (PartnerLink.name.ilike(pattern)) | (PartnerLink.code.ilike(pattern))
            )

        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "id": link.id,
                "name": link.name,
                "code": link.code,
                "url": self.build_url(link.code),
                "is_active": bool(link.is_active),
                "created_at": link.created_at,
                "new_users": int(new_users or 0),
                "paid_topups": int(paid_topups or 0),
                "paid_amount": int(paid_amount or 0),
            }
            for link, new_users, paid_topups, paid_amount in rows
        ]

    async def get_link_details(self, *, link_id: int) -> dict | None:
        link = await self.session.get(PartnerLink, link_id)
        if not link:
            return None

        user_payments_sq = (
            select(
                Transaction.user_id.label("user_id"),
                func.count(Transaction.id).label("paid_topups"),
                func.coalesce(func.sum(Transaction.amount), 0).label("paid_amount"),
                func.max(Transaction.paid_at).label("last_paid_at"),
                func.max(Transaction.amount).label("max_paid_amount"),
            )
            .where(Transaction.paid.is_(True))
            .group_by(Transaction.user_id)
            .subquery()
        )

        users_stmt = (
            select(
                PartnerAttribution.user_id,
                User.tg_id,
                User.username,
                User.created_at,
                PartnerAttribution.created_at,
                func.coalesce(user_payments_sq.c.paid_topups, 0),
                func.coalesce(user_payments_sq.c.paid_amount, 0),
                user_payments_sq.c.last_paid_at,
                func.coalesce(user_payments_sq.c.max_paid_amount, 0),
            )
            .join(User, User.id == PartnerAttribution.user_id)
            .outerjoin(user_payments_sq, user_payments_sq.c.user_id == PartnerAttribution.user_id)
            .where(PartnerAttribution.partner_link_id == link_id)
            .order_by(
                func.coalesce(user_payments_sq.c.paid_amount, 0).desc(),
                PartnerAttribution.created_at.desc(),
            )
        )

        recent_payments_stmt = (
            select(
                Transaction.id,
                Transaction.user_id,
                User.tg_id,
                User.username,
                Transaction.amount,
                Transaction.payment_system,
                Transaction.paid_at,
                PartnerAttribution.created_at,
            )
            .join(PartnerAttribution, PartnerAttribution.user_id == Transaction.user_id)
            .join(User, User.id == Transaction.user_id)
            .where(
                PartnerAttribution.partner_link_id == link_id,
                Transaction.paid.is_(True),
                Transaction.paid_at.is_not(None),
            )
            .order_by(Transaction.paid_at.desc(), Transaction.id.desc())
            .limit(20)
        )

        users_rows = (await self.session.execute(users_stmt)).all()
        recent_payment_rows = (await self.session.execute(recent_payments_stmt)).all()

        total_paid_users = sum(1 for row in users_rows if int(row[5] or 0) > 0)
        total_converted_amount = sum(int(row[6] or 0) for row in users_rows)
        total_converted_topups = sum(int(row[5] or 0) for row in users_rows)
        last_payment_at = None
        for row in recent_payment_rows:
            paid_at = row[6]
            if paid_at and (last_payment_at is None or paid_at > last_payment_at):
                last_payment_at = paid_at

        return {
            "link": {
                "id": link.id,
                "name": link.name,
                "code": link.code,
                "url": self.build_url(link.code),
                "is_active": bool(link.is_active),
                "created_at": link.created_at,
            },
            "summary": {
                "attributed_users": len(users_rows),
                "paid_users": total_paid_users,
                "paid_topups": total_converted_topups,
                "paid_amount": total_converted_amount,
                "last_payment_at": last_payment_at,
            },
            "users": [
                {
                    "user_id": int(user_id),
                    "tg_id": tg_id,
                    "username": username,
                    "user_created_at": user_created_at,
                    "attributed_at": attributed_at,
                    "paid_topups": int(paid_topups or 0),
                    "paid_amount": int(paid_amount or 0),
                    "last_paid_at": last_paid_at,
                    "max_paid_amount": int(max_paid_amount or 0),
                }
                for user_id, tg_id, username, user_created_at, attributed_at, paid_topups, paid_amount, last_paid_at, max_paid_amount in users_rows
            ],
            "recent_payments": [
                {
                    "transaction_id": int(tx_id),
                    "user_id": int(user_id),
                    "tg_id": tg_id,
                    "username": username,
                    "amount": int(amount or 0),
                    "payment_system": payment_system,
                    "paid_at": paid_at,
                    "attributed_at": attributed_at,
                }
                for tx_id, user_id, tg_id, username, amount, payment_system, paid_at, attributed_at in recent_payment_rows
            ],
        }
