"""Dashboard totals: one aggregate query per table, without caching account data."""
from datetime import timedelta

from sqlalchemy import func, select

from backend.database.models import User, Transaction, Subscription, SubStatus


async def dashboard_totals(session, now):
    day_start = now - timedelta(days=1)
    month_start = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    active = (Subscription.status == SubStatus.active) & (Subscription.current_period_end > now)
    users = (await session.execute(select(
        func.count(User.id).label("total_users"),
        func.count(User.id).filter(User.banned.is_(True)).label("banned_users"),
        func.count(User.id).filter(User.created_at >= day_start).label("new_users_today"),
        func.coalesce(func.sum(User.balance),0).label("total_balance"),
    ))).mappings().one()
    transactions = (await session.execute(select(
        func.count(Transaction.id).filter(Transaction.paid.is_(False)).label("unpaid_transactions"),
        func.count(Transaction.id).filter(Transaction.paid.is_(True)).label("paid_transactions"),
        func.coalesce(func.sum(Transaction.amount).filter(Transaction.paid.is_(True)),0).label("total_revenue"),
        func.coalesce(func.sum(Transaction.amount).filter(Transaction.paid.is_(True),Transaction.paid_at>=day_start),0).label("today_revenue"),
        func.coalesce(func.sum(Transaction.amount).filter(Transaction.paid.is_(True),Transaction.paid_at>=month_start),0).label("month_revenue"),
    ))).mappings().one()
    subscriptions = (await session.execute(select(
        func.count(Subscription.id).filter(active).label("active_subscriptions"),
        func.count(func.distinct(Subscription.user_id)).filter(active).label("subscribed_users"),
        func.count(Subscription.id).filter(active,Subscription.current_period_end<=now+timedelta(days=7)).label("expiring_subscriptions"),
    ))).mappings().one()
    return {key:int(value or 0) for row in (users,transactions,subscriptions) for key,value in row.items()}
