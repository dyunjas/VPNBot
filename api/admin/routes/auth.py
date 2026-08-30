import time
import hmac
import hashlib
import secrets
from fastapi import APIRouter, Request, Response
from ..common import *
from backend.database.models import Admin
from api.cabinet.common import _smtp_send_code
from api.admin.audit import record_login_event

router = APIRouter()
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_SEC = 300
_LOGIN_MAX_ATTEMPTS = 5
_ADMIN_COOKIE_NAME = "admin_access_token"
_PASSWORD_HASH_ALG = "pbkdf2_sha256"
_PASSWORD_HASH_ITERATIONS = 260000
_ADMIN_OTP_TTL_SEC = 600
_ADMIN_OTP_CHALLENGES: dict[str, dict] = {}
_ADMIN_OTP_MAX_ATTEMPTS = 5


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


def hash_admin_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        _PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{_PASSWORD_HASH_ALG}${_PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_admin_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        alg, iterations_raw, salt, expected = password_hash.split("$", 3)
        if alg != _PASSWORD_HASH_ALG:
            return False
        iterations = int(iterations_raw)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (TypeError, ValueError):
        return False


def _issue_admin_otp(login: str, role: str, admin_id: int | None, email: str) -> str:
    challenge_id = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1000000):06d}"
    _ADMIN_OTP_CHALLENGES[challenge_id] = {"login": login, "role": role, "admin_id": admin_id, "email": email, "code": code, "expires_at": time.time() + _ADMIN_OTP_TTL_SEC, "attempts": 0}
    try:
        _smtp_send_code(email, code, purpose="admin_login")
    except Exception:
        _ADMIN_OTP_CHALLENGES.pop(challenge_id, None)
        raise
    return challenge_id


class AdminLoginVerifyPayload(BaseModel):
    challenge_id: str
    code: str


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

@router.post("/auth/login")
async def admin_auth_login(payload: LoginPayload, request: Request, response: Response):
    expected_login = (settings.ADMIN_WEB_EMAIL or settings.ADMIN_WEB_LOGIN or "").strip().lower()
    expected_password = (settings.ADMIN_WEB_PASSWORD or "").strip()
    key = _login_rate_key(request, payload.email)
    if not _login_allowed(key):
        await record_login_event(request, admin_id=None, username=login, email=login, success=False, reason="rate_limited")
        raise HTTPException(status_code=429, detail="Too many login attempts")

    login = payload.email.strip().lower()
    is_master_login = bool(expected_login and expected_password) and hmac.compare_digest(login, expected_login)
    if is_master_login and hmac.compare_digest(payload.password, expected_password):
        _LOGIN_ATTEMPTS.pop(key, None)
        email = (settings.ADMIN_WEB_EMAIL or "").strip().lower()
        if not email:
            await record_login_event(request, admin_id=None, username=login, email=login, success=False, reason="email_not_configured")
            raise HTTPException(status_code=503, detail="ADMIN_WEB_EMAIL is not configured")
        await record_login_event(request, admin_id=None, username=login, email=email, success=False, reason="password_accepted_2fa_pending")
        return {"ok": True, "requires_2fa": True, "challenge_id": _issue_admin_otp(login, "superadmin", None, email), "email_hint": email[:2] + "***" + email[email.find("@"):]} 

    admin = None
    async with async_session() as session:
        admin = (
            await session.execute(
                select(Admin).where(
                    func.lower(Admin.email) == login.lower(),
                    Admin.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    role = admin.role.value if admin and hasattr(admin.role, "value") else str(admin.role) if admin else ""
    if not admin or not verify_admin_password(payload.password, admin.password_hash):
        await record_login_event(request, admin_id=admin.id if admin else None, username=admin.username if admin else login, email=admin.email if admin else login, success=False, reason="invalid_credentials")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    email = admin.email or ""
    if not email:
        await record_login_event(request, admin_id=admin.id, username=admin.username, email=None, success=False, reason="email_not_configured")
        raise HTTPException(status_code=400, detail="Admin email is not configured")

    _LOGIN_ATTEMPTS.pop(key, None)
    await record_login_event(request, admin_id=admin.id, username=admin.username, email=email, success=False, reason="password_accepted_2fa_pending")
    return {"ok": True, "requires_2fa": True, "challenge_id": _issue_admin_otp(admin.username, role, admin.id, email), "email_hint": email[:2] + "***" + email[email.find("@"):]} 


@router.post("/auth/verify-2fa")
async def admin_auth_verify_2fa(payload: AdminLoginVerifyPayload, request: Request, response: Response):
    challenge = _ADMIN_OTP_CHALLENGES.get(payload.challenge_id)
    if not challenge or float(challenge["expires_at"]) < time.time():
        await record_login_event(request, admin_id=None, username=None, email=None, success=False, reason="invalid_or_expired_2fa")
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")
    challenge["attempts"] = int(challenge.get("attempts", 0)) + 1
    if challenge["attempts"] > _ADMIN_OTP_MAX_ATTEMPTS:
        _ADMIN_OTP_CHALLENGES.pop(payload.challenge_id, None)
        await record_login_event(request, admin_id=challenge.get("admin_id"), username=challenge.get("login"), email=challenge.get("email"), success=False, reason="2fa_rate_limited")
        raise HTTPException(status_code=429, detail="Too many verification attempts")
    if not hmac.compare_digest(str(challenge["code"]), payload.code.strip()):
        if challenge["attempts"] >= _ADMIN_OTP_MAX_ATTEMPTS:
            _ADMIN_OTP_CHALLENGES.pop(payload.challenge_id, None)
        await record_login_event(request, admin_id=challenge.get("admin_id"), username=challenge.get("login"), email=challenge.get("email"), success=False, reason="invalid_2fa")
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")
    _ADMIN_OTP_CHALLENGES.pop(payload.challenge_id, None)
    await record_login_event(request, admin_id=challenge.get("admin_id"), username=challenge.get("login"), email=challenge.get("email"), success=True, reason="authenticated")
    access_token = _create_admin_access_token(challenge["login"], role=challenge["role"], admin_id=challenge["admin_id"])
    max_age = max(int(settings.ADMIN_WEB_JWT_EXPIRE_HOURS or 12), 1) * 3600
    response.set_cookie(
        key=_ADMIN_COOKIE_NAME,
        value=access_token,
        max_age=max_age,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return {"ok": True, "login": challenge["login"], "role": challenge["role"]}


@router.get("/auth/me")
async def admin_auth_me(auth=Depends(require_admin_auth)):
    username = auth.get("sub")
    email = None
    if auth.get("admin_id"):
        async with async_session() as session:
            admin = await session.scalar(select(Admin).where(Admin.id == auth.get("admin_id")))
            if admin:
                username, email = admin.username, admin.email
    return {"ok": True, "login": auth.get("sub"), "username": username, "email": email, "scope": auth.get("scope"), "role": auth.get("role")}


@router.post("/auth/logout")
async def admin_auth_logout(response: Response):
    response.delete_cookie(key=_ADMIN_COOKIE_NAME, path="/", samesite="lax")
    return {"ok": True}


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
            "users_chart": users_chart,
            "subscriptions_chart": subscriptions_chart,
            "payments_chart": payments_chart,
            "activation_chart": activation_chart,
            "payments_chart_period": chart_period,
            "payments_chart_mode": chart_mode,
        },
    }


