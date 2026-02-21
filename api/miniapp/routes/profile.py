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
            "hint": "���������� ������ � ��������� �����. ������ ����������� ����� ��� ��������.",
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
        vpn_service = VPNService(session, xray_auth_token=XRAY_AUTH_TOKEN)

        try:
            subscription = await sub_service.get_active_subscription(user.id)
        except SubscriptionNotFound:
            return {
                "ok": True,
                "has_subscription": False,
                "statusText": "��� �������� ��������.",
                "active_keys": 0,
                "subscription_token": user.subscription_token,
                "subscription_url": (
                    f"https://{settings.PUBLIC_BASE_URL}/sub/{user.subscription_token}"
                    if user.subscription_token
                    else None
                ),
            }

        active_keys = await vpn_service.list_active_keys(user.id)

        sub_token = user.subscription_token
        sub_url = f"https://{settings.PUBLIC_BASE_URL}/sub/{sub_token}" if sub_token else None

        plan = subscription.plan
        status_text = (
            f"�����: {plan.name} � ������: {len(active_keys)}\n"
            f"�������� ��: {subscription.current_period_end.strftime('%d.%m.%Y %H:%M')}"
        )

        return {
            "ok": True,
            "has_subscription": True,
            "statusText": status_text,
            "active_keys": len(active_keys),
            "subscription_token": sub_token,
            "subscription_url": sub_url,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "price": plan.price,
                "period_days": plan.period_days,
                "gb_limit": int(getattr(plan, "gb_limit", 0) or 0),
                "device_limit": int(getattr(plan, "device_limit", 0) or 0),
            },
            "subscription": {
                "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                "status": subscription.status.value if subscription.status else None,
                "gb_left": str(subscription.gb_left) if subscription.gb_left is not None else None,
                "devices_limit": int(getattr(subscription, "devices_limit", 0) or 0),
                "devices_left": int(getattr(subscription, "devices_left", 0) or 0),
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
                "subscription_token": user.subscription_token,
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
