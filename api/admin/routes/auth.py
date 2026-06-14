from fastapi import APIRouter
from fastapi import Request
import time
from ..common import *

router = APIRouter()
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_SEC = 300
_LOGIN_MAX_ATTEMPTS = 5


def _login_rate_key(request: Request, login: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{login.strip().lower()}"


def _login_allowed(key: str) -> bool:
    now = time.time()
    attempts = [ts for ts in _LOGIN_ATTEMPTS.get(key, []) if now - ts < _LOGIN_WINDOW_SEC]
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        _LOGIN_ATTEMPTS[key] = attempts
        return False
    attempts.append(now)
    _LOGIN_ATTEMPTS[key] = attempts
    return True


def _shift_month_start(dt: datetime, months_delta: int) -> datetime:
    month_index = (dt.year * 12 + (dt.month - 1)) + months_delta
    year = month_index // 12
    month = month_index % 12 + 1
    return dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)

@router.post("/auth/login")
async def admin_auth_login(payload: LoginPayload, request: Request):
    expected_login = (settings.ADMIN_WEB_LOGIN or "").strip()
    expected_password = (settings.ADMIN_WEB_PASSWORD or "").strip()
    if not expected_login or not expected_password:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_WEB_LOGIN and ADMIN_WEB_PASSWORD must be configured",
        )
    if payload.login != expected_login:
        key = _login_rate_key(request, payload.login)
        if not _login_allowed(key):
            raise HTTPException(status_code=429, detail="Too many login attempts")
    if payload.login != expected_login or payload.password != expected_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = _create_admin_access_token(payload.login)
    return {"ok": True, "access_token": access_token, "token_type": "bearer"}


@router.get("/auth/me")
async def admin_auth_me(auth=Depends(require_admin_auth)):
    return {"ok": True, "login": auth.get("sub"), "scope": auth.get("scope")}


@router.get("/health", dependencies=[Depends(require_admin_auth)])
async def admin_health():
    return {"ok": True, "service": "admin-api"}


@router.get("/stats", dependencies=[Depends(require_admin_auth)])
async def admin_stats(chart_period: Literal["14d", "30d", "12m"] = Query(default="14d")):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if chart_period == "30d":
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
    async with async_session() as session:
        total_users = int(await session.scalar(select(func.count(User.id))) or 0)
        banned_users = int(await session.scalar(select(func.count(User.id)).where(User.banned.is_(True))) or 0)
        active_subscriptions = int(
            await session.scalar(
                select(func.count(Subscription.id)).where(
                    Subscription.status == SubStatus.active,
                    Subscription.current_period_end > now,
                )
            )
            or 0
        )
        active_keys = 0
        total_servers = 0
        total_devices = 0
        paid_tx = int(
            await session.scalar(select(func.count(Transaction.id)).where(Transaction.paid.is_(True)))
            or 0
        )
        total_revenue = int(
            await session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.paid.is_(True))
            )
            or 0
        )
        month_revenue = int(
            await session.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.paid.is_(True),
                    Transaction.paid_at.is_not(None),
                    Transaction.paid_at >= month_start,
                )
            )
            or 0
        )
        chart_rows = (
            await session.execute(
                select(Transaction.paid_at, Transaction.amount).where(
                    Transaction.paid.is_(True),
                    Transaction.paid_at.is_not(None),
                    Transaction.paid_at >= chart_start,
                )
            )
        ).all()

    payments_buckets: dict[str, dict[str, str | int]] = {}
    if chart_mode == "month":
        for offset in range(bucket_count):
            month_dt = _shift_month_start(chart_start, offset)
            key = f"{month_dt.year:04d}-{month_dt.month:02d}"
            payments_buckets[key] = {
                "key": key,
                "label": month_dt.strftime("%m.%y"),
                "amount": 0,
                "count": 0,
            }
    else:
        for offset in range(bucket_count):
            day = chart_start + timedelta(days=offset)
            key = day.date().isoformat()
            payments_buckets[key] = {
                "key": key,
                "label": day.strftime("%d.%m"),
                "amount": 0,
                "count": 0,
            }

    for paid_at, amount in chart_rows:
        paid_dt = _as_aware_utc(paid_at)
        if not paid_dt:
            continue
        key = f"{paid_dt.year:04d}-{paid_dt.month:02d}" if chart_mode == "month" else paid_dt.date().isoformat()
        if key not in payments_buckets:
            continue
        payments_buckets[key]["amount"] = int(payments_buckets[key]["amount"]) + int(amount or 0)
        payments_buckets[key]["count"] = int(payments_buckets[key]["count"]) + 1

    payments_chart = [
        {
            "key": key,
            "label": str(values["label"]),
            "amount": int(values["amount"]),
            "count": int(values["count"]),
        }
        for key, values in payments_buckets.items()
    ]

    return {
        "ok": True,
        "stats": {
            "total_users": total_users,
            "banned_users": banned_users,
            "active_subscriptions": active_subscriptions,
            "active_keys": active_keys,
            "total_servers": total_servers,
            "total_devices": total_devices,
            "paid_transactions": paid_tx,
            "total_revenue": total_revenue,
            "month_revenue": month_revenue,
            "month_start": month_start.isoformat(),
            "payments_chart": payments_chart,
            "payments_chart_period": chart_period,
            "payments_chart_mode": chart_mode,
        },
    }


