from __future__ import annotations

import csv
from io import StringIO

from fastapi import APIRouter
from fastapi.responses import Response

from ..common import *

router = APIRouter()


def _csv_safe_cell(value: object) -> object:
    return "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value


def _csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(headers)
    writer.writerows([_csv_safe_cell(value) for value in row] for row in rows)
    content = "\ufeff" + buffer.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/users", dependencies=[Depends(require_support_auth)])
async def admin_export_users(
    search: str | None = Query(default=None),
    banned: Literal["all", "only", "exclude"] = Query(default="all"),
):
    async with async_session() as session:
        active_sub_sq = (
            select(
                Subscription.user_id.label("user_id"),
                func.max(Subscription.current_period_end).label("subscription_end"),
            )
            .where(Subscription.status == SubStatus.active)
            .group_by(Subscription.user_id)
            .subquery()
        )
        stmt = select(User, active_sub_sq.c.subscription_end).outerjoin(active_sub_sq, active_sub_sq.c.user_id == User.id)

        if banned == "only":
            stmt = stmt.where(User.banned.is_(True))
        elif banned == "exclude":
            stmt = stmt.where(User.banned.is_(False))

        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            stmt = stmt.where(
                or_(
                    cast(User.id, String).ilike(pattern),
                    cast(User.tg_id, String).ilike(pattern),
                    func.coalesce(User.username, "").ilike(pattern),
                    func.coalesce(User.email, "").ilike(pattern),
                )
            )

        rows = (await session.execute(stmt.order_by(User.id.asc()))).all()

    return _csv_response(
        "users.csv",
        ["id", "tg_id", "username", "email", "balance", "banned", "subscription_end", "remnawave_uuid", "created_at"],
        [
            [
                user.id,
                user.tg_id,
                user.username or "",
                user.email or "",
                int(user.balance or 0),
                bool(user.banned),
                _to_iso(subscription_end),
                user.remnawave_user_uuid or "",
                _to_iso(user.created_at),
            ]
            for user, subscription_end in rows
        ],
    )


@router.get("/export/transactions", dependencies=[Depends(require_support_auth)])
async def admin_export_transactions(
    paid: Literal["all", "paid", "unpaid"] = Query(default="all"),
    payment_system: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    async with async_session() as session:
        stmt = select(Transaction, User.tg_id, User.username).join(User, User.id == Transaction.user_id)
        if paid == "paid":
            stmt = stmt.where(Transaction.paid.is_(True))
        elif paid == "unpaid":
            stmt = stmt.where(Transaction.paid.is_(False))
        if payment_system:
            stmt = stmt.where(Transaction.payment_system == payment_system.strip())
        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            stmt = stmt.where(
                or_(
                    cast(Transaction.id, String).ilike(pattern),
                    cast(Transaction.user_id, String).ilike(pattern),
                    cast(User.tg_id, String).ilike(pattern),
                    func.coalesce(User.username, "").ilike(pattern),
                    func.coalesce(Transaction.transaction_id, "").ilike(pattern),
                )
            )
        rows = (await session.execute(stmt.order_by(Transaction.created_at.desc()))).all()

    return _csv_response(
        "transactions.csv",
        ["id", "provider_id", "user_id", "tg_id", "username", "amount", "payment_system", "paid", "created_at", "paid_at"],
        [
            [
                tx.id,
                tx.transaction_id,
                tx.user_id,
                tg_id,
                username or "",
                int(tx.amount or 0),
                tx.payment_system,
                bool(tx.paid),
                _to_iso(tx.created_at),
                _to_iso(tx.paid_at),
            ]
            for tx, tg_id, username in rows
        ],
    )


@router.get("/export/subscriptions", dependencies=[Depends(require_support_auth)])
async def admin_export_subscriptions(
    status: Literal["all", "active", "past_due", "expired", "canceled"] = Query(default="all"),
    search: str | None = Query(default=None),
):
    async with async_session() as session:
        stmt = (
            select(Subscription, User.tg_id, User.username, SubscriptionPlan.name, SubscriptionPlan.price)
            .join(User, User.id == Subscription.user_id)
            .outerjoin(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id)
        )
        if status != "all":
            stmt = stmt.where(Subscription.status == SubStatus(status))
        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            stmt = stmt.where(
                or_(
                    cast(Subscription.id, String).ilike(pattern),
                    cast(Subscription.user_id, String).ilike(pattern),
                    cast(User.tg_id, String).ilike(pattern),
                    func.coalesce(User.username, "").ilike(pattern),
                )
            )
        rows = (await session.execute(stmt.order_by(Subscription.current_period_end.desc()))).all()

    return _csv_response(
        "subscriptions.csv",
        [
            "id",
            "user_id",
            "tg_id",
            "username",
            "plan_id",
            "plan_name",
            "plan_price",
            "status",
            "auto_renew",
            "device_limit",
            "gb_left",
            "current_period_start",
            "current_period_end",
            "next_renewal_at",
            "created_at",
        ],
        [
            [
                sub.id,
                sub.user_id,
                tg_id,
                username or "",
                sub.plan_id,
                plan_name or "",
                int(plan_price or 0) if plan_price is not None else "",
                sub.status.value if sub.status else "",
                bool(sub.auto_renew),
                int(sub.device_limit or 0),
                int(sub.gb_left or 0),
                _to_iso(sub.current_period_start),
                _to_iso(sub.current_period_end),
                _to_iso(sub.next_renewal_at),
                _to_iso(sub.created_at),
            ]
            for sub, tg_id, username, plan_name, plan_price in rows
        ],
    )


@router.get("/export/referrals", dependencies=[Depends(require_support_auth)])
async def admin_export_referrals(search: str | None = Query(default=None)):
    async with async_session() as session:
        stmt = select(ReferralAccount, User.tg_id, User.username).join(User, User.id == ReferralAccount.user_id)
        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            stmt = stmt.where(
                or_(
                    cast(ReferralAccount.user_id, String).ilike(pattern),
                    cast(User.tg_id, String).ilike(pattern),
                    func.coalesce(User.username, "").ilike(pattern),
                )
            )
        rows = (await session.execute(stmt.order_by(ReferralAccount.created_at.desc()))).all()

    return _csv_response(
        "referrals.csv",
        ["id", "user_id", "tg_id", "username", "invited_count", "referral_balance", "referral_percent", "created_at"],
        [
            [
                acc.id,
                acc.user_id,
                tg_id,
                username or "",
                int(acc.invited_count or 0),
                int(acc.referral_balance or 0),
                int(acc.referral_percent or 0),
                _to_iso(acc.created_at),
            ]
            for acc, tg_id, username in rows
        ],
    )


@router.get("/export/promocodes", dependencies=[Depends(require_superadmin_auth)])
async def admin_export_promocodes():
    async with async_session() as session:
        promos = (await session.execute(select(Promocode).order_by(Promocode.created_at.desc()))).scalars().all()
        used_counts = {
            int(pid): int(cnt)
            for pid, cnt in (
                await session.execute(
                    select(PromocodeActivation.promocode_id, func.count(PromocodeActivation.id))
                    .group_by(PromocodeActivation.promocode_id)
                )
            ).all()
        }

    return _csv_response(
        "promocodes.csv",
        ["id", "code", "amount", "usages_left", "used_count", "is_activated", "activated_at", "created_at"],
        [
            [
                promo.id,
                promo.code,
                int(promo.amount or 0),
                int(promo.usages or 0),
                used_counts.get(promo.id, 0),
                bool(promo.is_activated),
                _to_iso(promo.activated_at),
                _to_iso(promo.created_at),
            ]
            for promo in promos
        ],
    )
