from fastapi import APIRouter
from ..common import *

router = APIRouter()

@router.post("/auth/login")
async def admin_auth_login(payload: LoginPayload):
    expected_login = (settings.ADMIN_WEB_LOGIN or "").strip()
    expected_password = (settings.ADMIN_WEB_PASSWORD or "").strip()
    if not expected_login or not expected_password:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_WEB_LOGIN and ADMIN_WEB_PASSWORD must be configured",
        )
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
async def admin_stats():
    now = datetime.now(timezone.utc)
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
        },
    }


