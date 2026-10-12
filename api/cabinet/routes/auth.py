from __future__ import annotations

import secrets
import hashlib
import json
import time
import re
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from api.cabinet.common import (
    Bot,
    CompleteRegistrationPayload,
    InitPayload,
    JSONResponse,
    REFRESH_COOKIE,
    RegisterPayload,
    Request,
    SendEmailCodePayload,
    SendTelegramCodePayload,
    User,
    VerifyCodePayload,
    _create_access_token,
    _create_refresh_token,
    _consume_otp,
    _decode_token,
    _validate_user_session,
    _get_tg_user,
    _get_user,
    _otp_send_allowed,
    _otp_send_retry_after,
    _pop_otp,
    _put_otp,
    _smtp_send_code,
    async_session,
    bot,
    require_cabinet_auth,
    settings,
)
from backend.core.telegram import create_telegram_session
from backend.core.logger_config import logger
from backend.services.remnawave_service import RemnaWaveService
from backend.services.subscription_service import SubscriptionService
from backend.database.models import SecurityRecord
from backend.services.admin_security import check_origin, rate_limit

router = APIRouter()
DEEPLINK_COOKIE = "cabinet_login_initiator"
DEEPLINK_TTL_SEC = 10 * 60
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


async def _set_refresh_cookie(response: JSONResponse, user_id: int) -> None:
    session_id = secrets.token_urlsafe(32)
    refresh = _create_refresh_token(user_id, session_id)
    async with async_session() as db:
        await _get_user(db, user_id)
        db.add(SecurityRecord(key="cabinet-session:" + hashlib.sha256(session_id.encode()).hexdigest(), kind="cabinet_session", expires_at=int(time.time()) + 30 * 86400,
                              data={"user_id": user_id, "refresh_hash": hashlib.sha256(refresh.encode()).hexdigest()}))
        await db.commit()
    body = json.loads(response.body)
    if "access_token" in body:
        body["access_token"] = _create_access_token(user_id, session_id)
        response.body = response.render(body)
        response.headers["content-length"] = str(len(response.body))
    response.set_cookie(key=REFRESH_COOKIE, value=refresh, httponly=True,
                        secure=str(settings.PUBLIC_BASE_URL or "").strip().startswith("https://"),
                        samesite="strict", max_age=30 * 86400, path="/")


def _public_cabinet_base() -> str:
    raw = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw}"


async def _put_deeplink(user_id: int, initiator: str) -> str:
    token = secrets.token_urlsafe(32)
    async with async_session() as db:
        db.add(SecurityRecord(key="deeplink:" + hashlib.sha256(token.encode()).hexdigest(), kind="deeplink", expires_at=int(time.time()) + DEEPLINK_TTL_SEC,
                              data={"user_id": user_id, "initiator_hash": hashlib.sha256(initiator.encode()).hexdigest()}))
        await db.commit()
    return token


async def _pop_deeplink(token: str, initiator: str) -> int | None:
    key = "deeplink:" + hashlib.sha256(token.encode()).hexdigest()
    async with async_session() as db:
        rec = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == key).with_for_update())
        if not rec or rec.kind != "deeplink" or rec.expires_at <= int(time.time()) or not secrets.compare_digest(rec.data.get("initiator_hash", ""), hashlib.sha256(initiator.encode()).hexdigest()):
            return None
        removed = await db.scalar(delete(SecurityRecord).where(SecurityRecord.key == key).returning(SecurityRecord.key))
        await db.commit()
        return int(rec.data["user_id"]) if removed else None


@router.post("/auth/register")
async def cabinet_register(payload: RegisterPayload):
    email = payload.email.strip().lower()
    if not email or len(email) > 320 or not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Укажите email")
    if not (payload.offer_accepted and payload.terms_accepted and payload.privacy_accepted):
        raise HTTPException(status_code=400, detail="Необходимо принять все документы")

    async with async_session() as session:
        existing_email = await session.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Пользователь с таким email уже зарегистрирован")

    if not await _otp_send_allowed("registration", email, cooldown_sec=60, window_sec=3600, max_sends=5):
        retry_after = await _otp_send_retry_after(
            "registration",
            email,
            cooldown_sec=60,
            window_sec=3600,
            max_sends=5,
        )
        raise HTTPException(status_code=429, detail=f"Повторите попытку через {retry_after} сек.")

    code = f"{secrets.randbelow(1000000):06d}"
    await _put_otp("registration", email, None, code)
    _smtp_send_code(email, code, purpose="bind")
    return {"ok": True, "message": "Код подтверждения отправлен"}


@router.post("/auth/register/verify")
async def cabinet_register_verify(payload: CompleteRegistrationPayload):
    email = payload.email.strip().lower()
    if not email or len(email) > 320 or not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Укажите корректный email")
    matched, _ = await _consume_otp("registration", email, payload.code, max_attempts=5)
    if not matched:
        raise HTTPException(status_code=400, detail="Неверный или просроченный код")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        existing_email = await session.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Пользователь с таким email уже зарегистрирован")

        user = User(
            tg_id=None,
            email=email,
            username=None,
            balance=0,
            banned=False,
            offer_accepted_at=now,
            terms_accepted_at=now,
            privacy_accepted_at=now,
        )
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Пользователь с таким email уже зарегистрирован") from exc

        trial_granted = False
        trial_subscription = None
        remnawave_provisioned = False
        remnawave = RemnaWaveService(session)
        try:
            trial_plan = await SubscriptionService(session).get_trial_plan()
            if trial_plan:
                trial_subscription = await SubscriptionService(session).activate_subscription(
                    user_id=user.id,
                    plan_id=trial_plan.id,
                    auto_renew=False,
                )
                trial_granted = True
                try:
                    await remnawave.get_subscription_url(user=user, subscription=trial_subscription)
                    remnawave_provisioned = True
                except Exception as exc:
                    logger.exception(
                        "[cabinet][register] trial remnawave sync failed user_id=%s subscription_id=%s: %s",
                        user.id,
                        trial_subscription.id,
                        exc,
                    )
            else:
                remnawave_provisioned = await remnawave.provision_web_user(user=user)
        except Exception as exc:
            logger.exception("[cabinet][register] trial provisioning failed user_id=%s: %s", user.id, exc)
            await session.rollback()
            try:
                remnawave_provisioned = await remnawave.provision_web_user(user=user)
            except Exception as provision_exc:
                logger.exception("[cabinet][register] remnawave provisioning failed user_id=%s: %s", user.id, provision_exc)

    response = JSONResponse(
        {
            "ok": True,
            "access_token": _create_access_token(user.id),
            "token_type": "bearer",
            "remnawave_provisioned": remnawave_provisioned,
            "trial_granted": trial_granted,
            "trial_subscription": {
                "id": trial_subscription.id,
                "plan_id": trial_subscription.plan_id,
                "current_period_end": trial_subscription.current_period_end.isoformat()
                if trial_subscription and trial_subscription.current_period_end
                else None,
            }
            if trial_subscription
            else None,
        }
    )
    await _set_refresh_cookie(response, user.id)
    return response


@router.post("/auth/send-email-code")
async def cabinet_send_email_code(payload: SendEmailCodePayload):
    email = payload.email.strip().lower()
    async with async_session() as session:
        res = await session.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user with this email not found")
    if not await _otp_send_allowed("email", email):
        raise HTTPException(status_code=429, detail="code already sent recently")

    code = f"{secrets.randbelow(1000000):06d}"
    await _put_otp("email", email, user.id, code)
    _smtp_send_code(email, code, purpose="login")
    return {"ok": True}


@router.post("/auth/send-telegram-code")
async def cabinet_send_telegram_code(payload: SendTelegramCodePayload):
    async with async_session() as session:
        res = await session.execute(select(User).where(User.tg_id == payload.tg_id))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user with this tg_id not found")
    if not await _otp_send_allowed(
        "telegram",
        str(payload.tg_id),
        cooldown_sec=60,
        window_sec=600,
        max_sends=3,
    ):
        retry_after = await _otp_send_retry_after(
            "telegram",
            str(payload.tg_id),
            cooldown_sec=60,
            window_sec=600,
            max_sends=3,
        )
        if retry_after >= 60:
            raise HTTPException(
                status_code=429,
                detail=f"too many telegram codes requested, try again in {retry_after} seconds",
            )
        raise HTTPException(status_code=429, detail="code already sent recently")

    code = f"{secrets.randbelow(1000000):06d}"
    await _put_otp("telegram", str(payload.tg_id), user.id, code)
    text = f"<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji>Код входа в кабинет: <code>{code}</code>"

    if bot is not None:
        await bot.send_message(chat_id=payload.tg_id, text=text, parse_mode="HTML")
        return {"ok": True}

    bot_token = (settings.BOT_TOKEN or "").strip()
    if not bot_token:
        raise HTTPException(status_code=503, detail="BOT_TOKEN is not configured")

    session = create_telegram_session()
    temp_bot = Bot(token=bot_token, session=session)
    try:
        await temp_bot.send_message(chat_id=payload.tg_id, text=text, parse_mode="HTML")
    finally:
        await temp_bot.session.close()
    return {"ok": True}


@router.post("/auth/deeplink/send")
async def cabinet_send_deeplink(payload: SendTelegramCodePayload, response: Response):
    async with async_session() as session:
        res = await session.execute(select(User).where(User.tg_id == payload.tg_id))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user with this tg_id not found")
        if bool(getattr(user, "banned", False)):
            raise HTTPException(status_code=403, detail="banned")

    if not await _otp_send_allowed(
        "deeplink",
        str(payload.tg_id),
        cooldown_sec=45,
        window_sec=600,
        max_sends=3,
    ):
        retry_after = await _otp_send_retry_after(
            "deeplink",
            str(payload.tg_id),
            cooldown_sec=45,
            window_sec=600,
            max_sends=3,
        )
        raise HTTPException(status_code=429, detail=f"deeplink already sent recently, try again in {retry_after} seconds")

    initiator = secrets.token_urlsafe(32)
    token = await _put_deeplink(user.id, initiator)
    response.set_cookie(DEEPLINK_COOKIE, initiator, httponly=True, secure=str(settings.PUBLIC_BASE_URL).startswith("https://"), samesite="strict", max_age=DEEPLINK_TTL_SEC, path="/")
    base = _public_cabinet_base()
    if not base:
        raise HTTPException(status_code=503, detail="PUBLIC_BASE_URL is not configured")
    link = f"{base}/cabinet/auth/deeplink/{quote(token)}"
    text = f"Вход в кабинет Lunet:\n\n{link}\n\nСсылка действует 10 минут."

    if bot is not None:
        await bot.send_message(chat_id=payload.tg_id, text=text)
        await _put_otp("deeplink", str(payload.tg_id), user.id, token)
        return {"ok": True}

    bot_token = (settings.BOT_TOKEN or "").strip()
    if not bot_token:
        raise HTTPException(status_code=503, detail="BOT_TOKEN is not configured")

    session = create_telegram_session()
    temp_bot = Bot(token=bot_token, session=session)
    try:
        await temp_bot.send_message(chat_id=payload.tg_id, text=text)
    finally:
        await temp_bot.session.close()
    await _put_otp("deeplink", str(payload.tg_id), user.id, token)
    return {"ok": True}


@router.post("/auth/deeplink/consume")
async def cabinet_consume_deeplink(payload: InitPayload, request: Request):
    token = str(payload.initData or "").strip()
    user_id = await _pop_deeplink(token, request.cookies.get(DEEPLINK_COOKIE, ""))
    if not user_id:
        raise HTTPException(status_code=400, detail="invalid or expired deeplink")

    async with async_session() as session:
        user = await _get_user(session, user_id)

    response = JSONResponse(
        {
            "ok": True,
            "access_token": _create_access_token(user.id),
            "token_type": "bearer",
        }
    )
    await _set_refresh_cookie(response, user.id)
    return response


@router.post("/auth/verify-code")
async def cabinet_verify_code(payload: VerifyCodePayload):
    if payload.channel == "email":
        identity = (payload.email or "").strip().lower()
        if not identity:
            raise HTTPException(status_code=400, detail="email is required")
        user_id = await _pop_otp("email", identity, payload.code)
    else:
        if payload.tg_id is None:
            raise HTTPException(status_code=400, detail="tg_id is required")
        user_id = await _pop_otp("telegram", str(payload.tg_id), payload.code)

    if not user_id:
        raise HTTPException(status_code=400, detail="invalid or expired code")

    response = JSONResponse({"ok": True, "access_token": _create_access_token(user_id), "token_type": "bearer"})
    await _set_refresh_cookie(response, user_id)
    return response


@router.post("/auth/telegram")
async def cabinet_telegram_auth(payload: InitPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = int(tg_user["id"])
    async with async_session() as db:
        insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
        consumed = await db.scalar(insert(SecurityRecord).values(key="telegram-login:" + hashlib.sha256(payload.initData.encode()).hexdigest(), kind="telegram_login", expires_at=int(time.time()) + 86400, data={})
            .on_conflict_do_nothing(index_elements=[SecurityRecord.key]).returning(SecurityRecord.key))
        await db.commit()
        if not consumed:
            raise HTTPException(401, "Telegram login proof has already been used")

    async with async_session() as session:
        res = await session.execute(select(User).where(User.tg_id == tg_id))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user not found, сначала зайдите в бота")
        if bool(getattr(user, "banned", False)):
            raise HTTPException(status_code=403, detail="banned")

        username = (tg_user.get("username") or "").strip() or None
        if username and username != getattr(user, "username", None):
            user.username = username
            await session.commit()

        response = JSONResponse(
            {
                "ok": True,
                "access_token": _create_access_token(user.id),
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "tg_id": user.tg_id,
                    "email": user.email,
                    "username": user.username,
                },
            }
        )
        await _set_refresh_cookie(response, user.id)
        return response


@router.post("/auth/refresh")
async def cabinet_refresh(request: Request):
    check_origin(request)
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(401, "Unauthorized")
    payload = _decode_token(token)
    if payload.get("scope") != "cabinet:refresh" or payload.get("kind") != "refresh":
        raise HTTPException(401, "Unauthorized")
    await rate_limit(request, "cabinet-refresh", str(payload["sub"]), maximum=30, window=60)
    key = "cabinet-session:" + hashlib.sha256(payload["sid"].encode()).hexdigest()
    async with async_session() as db:
        record = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == key).with_for_update())
        if not record or record.kind != "cabinet_session" or record.expires_at <= int(time.time()) or str(record.data.get("user_id")) != payload["sub"] or record.data.get("refresh_hash") != hashlib.sha256(token.encode()).hexdigest():
            raise HTTPException(401, "Unauthorized")
        user = await _get_user(db, int(payload["sub"]))
        new_refresh = _create_refresh_token(user.id, payload["sid"])
        record.data = {**record.data, "refresh_hash": hashlib.sha256(new_refresh.encode()).hexdigest()}
        expires_in = record.expires_at - int(time.time())
        await db.commit()
    response = JSONResponse({"ok": True, "access_token": _create_access_token(user.id, payload["sid"]), "token_type": "bearer"})
    response.set_cookie(REFRESH_COOKIE, new_refresh, httponly=True, secure=str(settings.PUBLIC_BASE_URL).startswith("https://"), samesite="strict", max_age=expires_in, path="/")
    return response


@router.post("/auth/logout")
async def cabinet_logout(request: Request):
    check_origin(request)
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        try:
            payload = _decode_token(token)
            if payload.get("scope") == "cabinet:refresh":
                async with async_session() as db:
                    await db.execute(delete(SecurityRecord).where(SecurityRecord.key == "cabinet-session:" + hashlib.sha256(payload["sid"].encode()).hexdigest()))
                    await db.commit()
        except HTTPException:
            pass
    response = JSONResponse({"ok": True})
    response.delete_cookie(key=REFRESH_COOKIE, path="/")
    return response


@router.get("/auth/me")
async def cabinet_auth_me(user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        return {"ok": True, "user": {"id": user.id, "tg_id": user.tg_id, "email": user.email, "username": user.username}}


@router.get("/auth/session")
async def cabinet_session(request: Request):
    """Read-only landing identity; never returns or refreshes authentication tokens."""
    origin = request.headers.get("origin")
    allowed_origins = {"https://lunet.pro", "https://www.lunet.pro"}
    headers = {"Cache-Control": "private, no-store", "Vary": "Origin"}
    if origin and origin not in allowed_origins and origin != str(request.base_url).rstrip("/"):
        return JSONResponse({"authenticated": False}, status_code=403, headers=headers)
    if origin in allowed_origins:
        headers.update({"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"})
    try:
        authorization = request.headers.get("authorization")
        user_id = None
        if authorization:
            try:
                user_id = await require_cabinet_auth(authorization)
            except HTTPException:
                pass
        if user_id is None:
            token = request.cookies.get(REFRESH_COOKIE)
            if not token:
                return JSONResponse({"authenticated": False}, headers=headers)
            payload = _decode_token(token)
            if payload.get("scope") != "cabinet:refresh":
                raise HTTPException(status_code=401, detail="Unauthorized")
            await _validate_user_session(payload)
            user_id = int(payload["sub"])
        async with async_session() as session:
            user = await _get_user(session, user_id)
            return JSONResponse({"authenticated": True, "user": {"username": user.username, "email": user.email}}, headers=headers)
    except (HTTPException, ValueError, KeyError, TypeError):
        return JSONResponse({"authenticated": False}, headers=headers)
