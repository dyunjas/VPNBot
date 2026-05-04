from fastapi import APIRouter

from ..common import *

router = APIRouter()


@router.post("/referral")
async def mini_referral(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        referral_url = f"https://t.me/{BOT_USERNAME}?start=ref_{user.tg_id}"

        return {
            "ok": True,
            "referral_url": referral_url,
            "hint": "Приглашайте друзей и получайте доход. Ссылка закреплена ниже для отправки.",
        }


@router.post("/setup")
async def mini_setup(payload: InitPayload):
    _ = _get_tg_user(payload.initData)
    return {"ok": True, "setup_url": SETUP_URL_FALLBACK}


@router.post("/status")
async def mini_status(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        sub_service = SubscriptionService(session)
        remnawave_service = RemnaWaveService(session)
        try:
            active_sub = await sub_service.get_active_subscription(user_id=user.id)
        except SubscriptionNotFound:
            return {
                "ok": True,
                "has_subscription": False,
                "statusText": "Нет активной подписки.",
                "active_keys": 0,
                "subscription_url": None,
            }

        remote = await remnawave_service.get_user_snapshot(user=user)
        if not isinstance(remote, dict):
            return {
                "ok": True,
                "has_subscription": False,
                "statusText": "Нет активной подписки.",
                "active_keys": 0,
                "subscription_url": None,
            }

        status = str(remote.get("status") or "")
        expire_at = remote.get("expireAt")
        sub_url = remote.get("subscriptionUrl") or remote.get("subscription_url")
        has_subscription = status in {"ACTIVE", "LIMITED"}

        status_text = (
            f"Статус: {status or 'UNKNOWN'}\n"
            f"Действует до: {expire_at or '—'}"
        )

        devices = await remnawave_service.get_user_hwid_devices(user=user)
        devices_used = len(devices)
        raw_device_limit = remote.get("hwidDeviceLimit")
        try:
            devices_limit = max(0, int(raw_device_limit)) if raw_device_limit is not None else 0
        except Exception:
            devices_limit = 0
        devices_left = max(devices_limit - devices_used, 0) if devices_limit > 0 else None

        user_traffic = remote.get("userTraffic") if isinstance(remote.get("userTraffic"), dict) else {}
        return {
            "ok": True,
            "has_subscription": bool(has_subscription),
            "statusText": status_text,
            "active_keys": 0,
            "subscription_url": sub_url,
            "plan": None,
            "subscription": {
                "current_period_start": None,
                "current_period_end": expire_at,
                "status": status or None,
                "token": getattr(active_sub, "subscription_token", None),
                "gb_left": None,
                "devices_limit": devices_limit,
                "devices_used": devices_used,
                "devices_left": devices_left,
            },
            "remnawave": {
                "uuid": remote.get("uuid"),
                "id": remote.get("id"),
                "username": remote.get("username"),
                "trafficLimitBytes": remote.get("trafficLimitBytes"),
                "trafficLimitStrategy": remote.get("trafficLimitStrategy"),
                "usedTrafficBytes": user_traffic.get("usedTrafficBytes"),
                "lifetimeUsedTrafficBytes": user_traffic.get("lifetimeUsedTrafficBytes"),
                "hwidDeviceLimit": remote.get("hwidDeviceLimit"),
            },
        }


@router.post("/profile")
async def mini_profile(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        tx_service = TransactionService(session)
        txs = await tx_service.list_by_user(user.id)
        txs = txs[:50]

        referral_service = ReferralService(session)
        referral_account = await referral_service.create_account(user.id)

        return {
            "ok": True,
            "user": {
                "tg_id": user.tg_id,
                "username": user.username,
                "balance": user.balance,
                "email": user.email,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "referral": {
                "balance": int(referral_account.referral_balance or 0),
                "percent": int(referral_account.referral_percent or 0),
                "invited_count": int(referral_account.invited_count or 0),
            },
            "transactions": [
                {
                    "id": t.id,
                    "amount": int(t.amount) if t.amount is not None else None,
                    "payment_system": t.payment_system,
                    "order_id": getattr(t, "order_id", None),
                    "paid": t.paid,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "paid_at": t.paid_at.isoformat() if t.paid_at else None,
                    "transaction_id": getattr(t, "transaction_id", None),
                }
                for t in txs
            ],
        }
