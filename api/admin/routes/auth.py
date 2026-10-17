from ..common import *
from backend.services.dashboard_stats import dashboard_totals
from api.admin.authentication import router

def _shift_month_start(dt: datetime, months_delta: int) -> datetime:
    month_index = (dt.year * 12 + (dt.month - 1)) + months_delta
    year = month_index // 12
    month = month_index % 12 + 1
    return dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _build_chart_buckets(chart_start: datetime, chart_mode: str, bucket_count: int) -> dict[str, dict[str, int | str]]:
    buckets: dict[str, dict[str, int | str]] = {}
    if chart_mode == "month":
        for offset in range(bucket_count):
            month_dt = _shift_month_start(chart_start, offset)
            key = f"{month_dt.year:04d}-{month_dt.month:02d}"
            buckets[key] = {
                "key": key,
                "label": month_dt.strftime("%m.%y"),
                "count": 0,
                "amount": 0,
            }
        return buckets

    for offset in range(bucket_count):
        day = chart_start + timedelta(days=offset)
        key = day.date().isoformat()
        buckets[key] = {
            "key": key,
            "label": day.strftime("%d.%m"),
            "count": 0,
            "amount": 0,
        }
    return buckets


def _chart_key_for_dt(dt: datetime, chart_mode: str) -> str:
    if chart_mode == "month":
        return f"{dt.year:04d}-{dt.month:02d}"
    return dt.date().isoformat()


def _fill_count_buckets(rows, buckets: dict[str, dict[str, int | str]], chart_mode: str) -> None:
    for row_dt in rows:
        dt = _as_aware_utc(row_dt)
        if not dt:
            continue
        key = _chart_key_for_dt(dt, chart_mode)
        bucket = buckets.get(key)
        if not bucket:
            continue
        bucket["count"] = int(bucket["count"]) + 1


def _fill_amount_buckets(rows, buckets: dict[str, dict[str, int | str]], chart_mode: str) -> None:
    for paid_at, amount in rows:
        dt = _as_aware_utc(paid_at)
        if not dt:
            continue
        key = _chart_key_for_dt(dt, chart_mode)
        bucket = buckets.get(key)
        if not bucket:
            continue
        bucket["amount"] = int(bucket["amount"]) + int(amount or 0)
        bucket["count"] = int(bucket["count"]) + 1

@router.get("/health", dependencies=[Depends(require_superadmin_auth)])
async def admin_health():
    return {"ok": True, "service": "admin-api"}


@router.get("/stats", dependencies=[Depends(require_superadmin_auth)])
async def admin_stats(chart_period: Literal["14d", "30d", "12m"] = Query(default="14d"), chart_from: str | None = Query(default=None), chart_to: str | None = Query(default=None)):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if chart_from or chart_to:
        try:
            chart_start = datetime.fromisoformat((chart_from or chart_to).strip()).replace(tzinfo=timezone.utc)
            chart_end = datetime.fromisoformat((chart_to or chart_from).strip()).replace(tzinfo=timezone.utc) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid chart date range")
        if chart_end <= chart_start or chart_end - chart_start > timedelta(days=366):
            raise HTTPException(status_code=400, detail="chart range must be between 1 and 366 days")
        chart_mode = "month" if (chart_end - chart_start).days > 62 else "day"
        bucket_count = 12 if chart_mode == "month" else (chart_end - chart_start).days
        if chart_mode == "month":
            chart_start = chart_start.replace(day=1)
    elif chart_period == "30d":
        chart_start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        chart_mode = "day"
        bucket_count = 30
    elif chart_period == "12m":
        chart_start = _shift_month_start(month_start, -11)
        chart_mode = "month"
        bucket_count = 12
    else:
        chart_start = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
        chart_mode = "day"
        bucket_count = 14
    chart_end = locals().get("chart_end", now + timedelta(seconds=1))
    async with async_session() as session:
        totals = await dashboard_totals(session,now)
        user_rows = (await session.execute(select(User.created_at).where(User.created_at >= chart_start, User.created_at < chart_end))).scalars().all()
        subscription_rows = (
            await session.execute(select(Subscription.created_at).where(Subscription.created_at >= chart_start, Subscription.created_at < chart_end))
        ).scalars().all()
        activation_subscription_rows = (
            await session.execute(
                select(Subscription.created_at)
                .join(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
                .where(
                    Subscription.created_at >= chart_start,
                    SubscriptionPlan.is_trial.is_(False),
                    Subscription.created_at < chart_end,
                )
            )
        ).scalars().all()
        payment_rows = (
            await session.execute(
                select(Transaction.paid_at, Transaction.amount).where(
                    Transaction.paid.is_(True),
                    Transaction.paid_at.is_not(None),
                    Transaction.paid_at >= chart_start,
                    Transaction.paid_at < chart_end,
                )
            )
        ).all()

    users_buckets = _build_chart_buckets(chart_start, chart_mode, bucket_count)
    subscriptions_buckets = _build_chart_buckets(chart_start, chart_mode, bucket_count)
    payments_buckets = _build_chart_buckets(chart_start, chart_mode, bucket_count)

    _fill_count_buckets(user_rows, users_buckets, chart_mode)
    activation_subscriptions_buckets = _build_chart_buckets(chart_start, chart_mode, bucket_count)

    _fill_count_buckets(subscription_rows, subscriptions_buckets, chart_mode)
    _fill_count_buckets(activation_subscription_rows, activation_subscriptions_buckets, chart_mode)
    _fill_amount_buckets(payment_rows, payments_buckets, chart_mode)

    users_chart = [
        {"key": key, "label": str(values["label"]), "count": int(values["count"])}
        for key, values in users_buckets.items()
    ]
    subscriptions_chart = [
        {"key": key, "label": str(values["label"]), "count": int(values["count"])}
        for key, values in subscriptions_buckets.items()
    ]
    payments_chart = [
        {
            "key": key,
            "label": str(values["label"]),
            "amount": int(values["amount"]),
            "count": int(values["count"]),
        }
        for key, values in payments_buckets.items()
    ]
    activation_chart = []
    for key in users_buckets.keys():
        users_count = int(users_buckets[key]["count"])
        subs_count = int(activation_subscriptions_buckets[key]["count"])
        rate = round((subs_count / users_count) * 100, 1) if users_count else 0.0
        activation_chart.append(
            {
                "key": key,
                "label": str(users_buckets[key]["label"]),
                "rate": rate,
                "users": users_count,
                "subscriptions": subs_count,
            }
        )

    return {
        "ok": True,
        "stats": {
            "total_users": totals["total_users"],
            "banned_users": totals["banned_users"],
            "new_users_today": totals["new_users_today"],
            "today_revenue": totals["today_revenue"],
            "expiring_subscriptions": totals["expiring_subscriptions"],
            "unpaid_transactions": totals["unpaid_transactions"],
            "total_balance": totals["total_balance"],
            "active_subscriptions": totals["active_subscriptions"],
            "subscribed_users": totals["subscribed_users"],
            "active_keys": 0,
            "total_servers": 0,
            "total_devices": 0,
            "paid_transactions": totals["paid_transactions"],
            "total_revenue": totals["total_revenue"],
            "month_revenue": totals["month_revenue"],
            "month_start": month_start.isoformat(),
            "users_chart": users_chart,
            "subscriptions_chart": subscriptions_chart,
            "payments_chart": payments_chart,
            "activation_chart": activation_chart,
            "payments_chart_period": chart_period,
            "payments_chart_mode": chart_mode,
        },
    }


