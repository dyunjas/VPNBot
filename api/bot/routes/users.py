from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.bot.common import (
    PartnerPayload,
    ReferrerPayload,
    SubscriptionService,
    TrialPayload,
    TRIAL_PLAN_ID,
    TgUserPayload,
    UsernamePayload,
    EmailPayload,
    UserNotFound,
    _get_user_or_404,
    _map_service_error,
    get_partner_service,
    get_referral_service,
    get_remnawave_service,
    get_subscription_service,
    get_user_service,
    require_bot_auth,
)
from backend.core.logger_config import logger

router = APIRouter(dependencies=[Depends(require_bot_auth)])


@router.post("/users/ensure")
async def ensure_user(payload: TgUserPayload, user_service=Depends(get_user_service)):
    user = await user_service.create_user(tg_id=payload.tg_id, username=payload.username)
    return {"ok": True, "user": {"id": user.id, "tg_id": user.tg_id, "username": user.username, "email": user.email, "balance": int(user.balance or 0), "banned": bool(getattr(user, "banned", False)), "referrer_id": getattr(user, "referrer_id", None)}, "is_new": bool(getattr(user, "created_at", None))}


@router.get("/users/by-tg/{tg_id}")
async def get_user_by_tg(tg_id: int, user_service=Depends(get_user_service)):
    user = await _get_user_or_404(user_service, tg_id)
    return {"ok": True, "user": {"id": user.id, "tg_id": user.tg_id, "username": user.username, "email": user.email, "balance": int(user.balance or 0), "banned": bool(getattr(user, "banned", False)), "referrer_id": getattr(user, "referrer_id", None)}}


@router.patch("/users/{user_id}/username")
async def set_username(user_id: int, payload: UsernamePayload, user_service=Depends(get_user_service)):
    await user_service.set_username(user_id, payload.username)
    return {"ok": True}


@router.patch("/users/{user_id}/email")
async def set_email(user_id: int, payload: EmailPayload, user_service=Depends(get_user_service)):
    try:
        await user_service.set_email(user_id, payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc) or "email already bound") from exc
    return {"ok": True}


@router.post("/users/{user_id}/referrer")
async def attach_referrer(user_id: int, payload: ReferrerPayload, referral_service=Depends(get_referral_service), user_service=Depends(get_user_service)):
    referrer = await _get_user_or_404(user_service, payload.referrer_tg_id)
    try:
        linked = await referral_service.attach_referrer(user_id=user_id, referrer_id=referrer.id)
    except Exception as e:
        raise _map_service_error(e)
    return {"ok": True, "linked": linked, "referrer": {"id": referrer.id, "tg_id": referrer.tg_id, "username": referrer.username}}


@router.post("/users/{user_id}/partner")
async def attach_partner(user_id: int, payload: PartnerPayload, partner_service=Depends(get_partner_service)):
    try:
        result = await partner_service.attach_user(user_id=user_id, code=payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid partner code") from exc
    return {"ok": True, "result": result}


@router.post("/users/{user_id}/trial")
async def grant_trial(user_id: int, user_service=Depends(get_user_service), subscription_service=Depends(get_subscription_service), remnawave_service=Depends(get_remnawave_service)):
    try:
        user = await user_service.get_by_id(user_id)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="user not found")
    try:
        sub = await subscription_service.activate_subscription(user_id=user.id, plan_id=TRIAL_PLAN_ID, auto_renew=False)
    except Exception as e:
        if "TooEarlyToRenew" in type(e).__name__:
            return {"ok": True, "granted": False, "reason": "too_early"}
        raise _map_service_error(e)
    try:
        await remnawave_service.get_subscription_url(user=user, subscription=sub)
    except Exception:
        logger.exception("[biz][subscription] trial remnawave sync failed user_id=%s subscription_id=%s", user_id, sub.id)
    return {"ok": True, "granted": True, "subscription": {"id": sub.id, "plan_id": sub.plan_id, "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None}}
