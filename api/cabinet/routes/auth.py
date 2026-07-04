from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from api.cabinet.common import (
    Bot,
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
    _decode_token,
    _get_tg_user,
    _get_user,
    _otp_send_allowed,
    _pop_otp,
    _put_otp,
    _smtp_send_code,
    async_session,
    bot,
    require_cabinet_auth,
    settings,
)
from backend.core.telegram import create_telegram_session

router = APIRouter()


@router.post("/auth/register")
async def cabinet_register(payload: RegisterPayload):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    tg_user = _get_tg_user(payload.initData)
    tg_id = int(tg_user["id"])

    async with async_session() as session:
        existing_email = await session.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="email already registered")

        existing_tg = await session.execute(select(User).where(User.tg_id == tg_id))
        user = existing_tg.scalar_one_or_none()
        if user:
            user.email = email
        else:
            user = User(tg_id=tg_id, email=email, username=None, balance=0, banned=False)
            session.add(user)
        await session.commit()
        await session.refresh(user)

    code = f"{secrets.randbelow(1000000):06d}"
    _put_otp("email", email, user.id, code)
    _smtp_send_code(email, code, purpose="bind")
    return {"ok": True, "message": "verification code sent"}


@router.post("/auth/send-email-code")
async def cabinet_send_email_code(payload: SendEmailCodePayload):
    email = payload.email.strip().lower()
    async with async_session() as session:
        res = await session.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user with this email not found")
    if not _otp_send_allowed("email", email):
        raise HTTPException(status_code=429, detail="code already sent recently")

    code = f"{secrets.randbelow(1000000):06d}"
    _put_otp("email", email, user.id, code)
    _smtp_send_code(email, code, purpose="login")
    return {"ok": True}


@router.post("/auth/send-telegram-code")
async def cabinet_send_telegram_code(payload: SendTelegramCodePayload):
    async with async_session() as session:
        res = await session.execute(select(User).where(User.tg_id == payload.tg_id))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="user with this tg_id not found")
    if not _otp_send_allowed("telegram", str(payload.tg_id)):
        raise HTTPException(status_code=429, detail="code already sent recently")

    code = f"{secrets.randbelow(1000000):06d}"
    _put_otp("telegram", str(payload.tg_id), user.id, code)
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


@router.post("/auth/verify-code")
async def cabinet_verify_code(payload: VerifyCodePayload):
    if payload.channel == "email":
        identity = (payload.email or "").strip().lower()
        if not identity:
            raise HTTPException(status_code=400, detail="email is required")
        user_id = _pop_otp("email", identity, payload.code)
    else:
        if payload.tg_id is None:
            raise HTTPException(status_code=400, detail="tg_id is required")
        user_id = _pop_otp("telegram", str(payload.tg_id), payload.code)

    if not user_id:
        raise HTTPException(status_code=400, detail="invalid or expired code")

    response = JSONResponse({"ok": True, "access_token": _create_access_token(user_id), "token_type": "bearer"})
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=_create_refresh_token(user_id),
        httponly=True,
        secure=str(settings.PUBLIC_BASE_URL or "").strip().startswith("https://"),
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/",
    )
    return response


@router.post("/auth/refresh")
async def cabinet_refresh(request: Request):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = _decode_token(refresh_token)
    if payload.get("scope") != "cabinet:refresh":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        user_id = int(payload.get("sub"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc
    return {"ok": True, "access_token": _create_access_token(user_id), "token_type": "bearer"}


@router.post("/auth/logout")
async def cabinet_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(key=REFRESH_COOKIE, path="/")
    return response


@router.get("/auth/me")
async def cabinet_auth_me(user_id: int = Depends(require_cabinet_auth)):
    async with async_session() as session:
        user = await _get_user(session, user_id)
        return {"ok": True, "user": {"id": user.id, "tg_id": user.tg_id, "email": user.email, "username": user.username}}
