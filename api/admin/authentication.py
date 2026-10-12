from __future__ import annotations

import asyncio
import base64
import hmac
import secrets
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update

from api.admin.audit import record_login_event
from api.cabinet.common import _smtp_send_code
from backend.core.config import settings
from backend.database.models import Admin, SecurityRecord
from backend.database.session import async_session
from backend.services import admin_security as security

router = APIRouter()


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class VerifyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: str = Field(min_length=32, max_length=128)
    code: str = Field(min_length=6, max_length=32)


class CodePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=6, max_length=32)


async def _audit(request, identity=None, success=False, reason="invalid_credentials"):
    identity = identity or {}
    await record_login_event(request, admin_id=identity.get("admin_id"), username=identity.get("sub"), email=identity.get("email"), success=success, reason=reason)


@router.post("/auth/login")
async def login(payload: LoginPayload, request: Request):
    security.check_origin(request)
    login = payload.email.strip().lower()
    await security.rate_limit(request, "admin-login", login)
    master_login = (settings.ADMIN_WEB_EMAIL or settings.ADMIN_WEB_LOGIN or "").strip().lower()
    email_code = None
    async with async_session() as db:
        admin = await db.scalar(select(Admin).where(func.lower(Admin.email) == login, Admin.is_active.is_(True)))
        # Always perform an expensive hash check, including master/unknown accounts.
        verified = await asyncio.to_thread(security.verify_password, payload.password, admin.password_hash if admin else None)
        master = bool(master_login and settings.ADMIN_WEB_PASSWORD) and hmac.compare_digest(login, master_login) and hmac.compare_digest(payload.password, settings.ADMIN_WEB_PASSWORD)
        owner = "master:" + security.digest(master_login) if master else f"admin:{admin.id}" if verified and admin else ""
        identity = await security.principal(db, owner) if owner else None
        if not identity or not identity.get("email"):
            await _audit(request)
            raise HTTPException(401, "Invalid credentials")
        # Legacy PBKDF2 passwords are upgraded only after a successful password check.
        if admin and not master and not admin.password_hash.startswith("$argon2id$"):
            admin.password_hash = await asyncio.to_thread(security.hash_password, payload.password)
            await db.flush()
            identity = await security.principal(db, owner)
        factor = await db.get(SecurityRecord, "factor:" + owner)
        challenge = secrets.token_urlsafe(32)
        data = {"owner": owner, "fingerprint": identity["fingerprint"], "attempts": 0, "mode": "totp" if factor else "email_enroll"}
        if not factor:
            email_code = f"{secrets.randbelow(1000000):06d}"
            data["email_hash"] = security.keyed("admin-enroll:" + challenge + ":" + email_code)
        await db.execute(security.delete(SecurityRecord).where(SecurityRecord.kind == "admin_challenge", SecurityRecord.expires_at <= security.now()))
        db.add(SecurityRecord(key="challenge:" + security.digest(challenge), kind="admin_challenge", data=data, expires_at=security.now() + security.CHALLENGE_TTL))
        await db.commit()
    if email_code:
        try:
            await asyncio.to_thread(_smtp_send_code, identity["email"], email_code, purpose="admin_login")
        except Exception:
            async with async_session() as db:
                await db.execute(security.delete(SecurityRecord).where(SecurityRecord.key == "challenge:" + security.digest(challenge)))
                await db.commit()
            raise HTTPException(503, "Unable to send verification code")
    await _audit(request, identity, reason="password_accepted_factor_pending")
    email = identity["email"]
    return {"ok": True, "requires_2fa": True, "challenge_id": challenge, "factor": data["mode"], "email_hint": email[:2] + "***" + email[email.find("@"): ]}


async def _verify_factor(db, factor: SecurityRecord, code: str) -> bool:
    previous = dict(factor.data)
    data = dict(factor.data)
    try:
        secret = security.cipher().decrypt(data["secret"].encode()).decode()
        counter = security.accepted_counter(secret, code, int(data.get("last_counter", -1)))
    except Exception:
        return False
    if counter is not None:
        data["last_counter"] = counter
    else:
        recovery = security.keyed("admin-recovery:" + code)
        codes = list(data.get("recovery", []))
        if recovery not in codes:
            return False
        codes.remove(recovery)
        data["recovery"] = codes
    # Compare-and-swap also makes replay rejection explicit across concurrent workers.
    changed = await db.scalar(update(SecurityRecord).where(SecurityRecord.key == factor.key, SecurityRecord.data == previous).values(data=data).returning(SecurityRecord.key))
    if not changed:
        return False
    await db.refresh(factor)
    return True


@router.post("/auth/verify-2fa")
async def verify(payload: VerifyPayload, request: Request, response: Response):
    security.check_origin(request)
    await security.rate_limit(request, "admin-2fa", payload.challenge_id, maximum=10)
    key = "challenge:" + security.digest(payload.challenge_id)
    async with async_session() as db:
        challenge = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == key).with_for_update())
        if not challenge or challenge.kind != "admin_challenge" or challenge.expires_at <= security.now():
            raise HTTPException(401, "Invalid or expired verification code")
        data = dict(challenge.data)
        identity = await security.principal(db, data["owner"])
        if not identity or identity["fingerprint"] != data["fingerprint"]:
            await db.delete(challenge);await db.commit()
            raise HTTPException(401, "Invalid or expired verification code")
        data["attempts"] += 1
        challenge.data = data
        if data["attempts"] > 5:
            await db.delete(challenge);await db.commit()
            raise HTTPException(429, "Too many verification attempts")
        factor = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == "factor:" + data["owner"]).with_for_update())
        recovery_codes = None
        if data["mode"] == "email_enroll":
            valid = hmac.compare_digest(data["email_hash"], security.keyed("admin-enroll:" + payload.challenge_id + ":" + payload.code))
            if valid and not factor:
                secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
                data.update(mode="enroll", secret=security.cipher().encrypt(secret.encode()).decode())
                data.pop("email_hash", None)
                data["attempts"] = 0
                await db.execute(update(SecurityRecord).where(SecurityRecord.key == key).values(data=dict(data)))
                await db.commit()
                # Email confirmation permits enrollment only, never an administrative session.
                return {"ok": True, "requires_2fa": True, "factor": "enroll", "challenge_id": payload.challenge_id,
                        "setup_secret": secret, "otpauth_uri": f"otpauth://totp/{quote('Lunet:' + identity['email'])}?secret={secret}&issuer=Lunet&algorithm=SHA1&digits=6&period=30"}
            valid = False
        elif data["mode"] == "enroll" and not factor:
            secret = security.cipher().decrypt(data["secret"].encode()).decode()
            counter = security.accepted_counter(secret, payload.code)
            valid = counter is not None
            if valid:
                recovery_codes = [secrets.token_urlsafe(18) for _ in range(8)]
                factor = SecurityRecord(key="factor:" + data["owner"], kind="admin_factor", expires_at=2**62,
                                        data={"secret": data["secret"], "last_counter": counter, "version": secrets.token_hex(16),
                                              "recovery": [security.keyed("admin-recovery:" + code) for code in recovery_codes]})
                db.add(factor)
        else:
            valid = data["mode"] == "totp" and factor is not None and await _verify_factor(db, factor, payload.code)
        if not valid:
            if data["attempts"] >= 5:
                await db.delete(challenge)
            await db.commit()
            await _audit(request, identity, reason="invalid_factor")
            raise HTTPException(401, "Invalid or expired verification code")
        consumed = await db.scalar(security.delete(SecurityRecord).where(SecurityRecord.key == key).returning(SecurityRecord.key))
        if not consumed:
            await db.rollback()
            raise HTTPException(401, "Invalid or expired verification code")
        token, csrf = await security.create_session(db, identity, factor)
        await db.commit()
    security.set_session_cookie(response, request, token)
    response.delete_cookie("admin_access_token", path="/")
    await _audit(request, identity, success=True, reason="authenticated")
    result = {"ok": True, "login": identity["sub"], "role": identity["role"], "csrf_token": csrf, "expires_in": security.SESSION_TTL}
    if recovery_codes:
        result["recovery_codes"] = recovery_codes
    return result


@router.get("/auth/me")
async def me(request: Request):
    identity = await security.validate_session(request)
    token = request.cookies.get(security.COOKIE) or request.cookies.get(security.DEV_COOKIE)
    return {"ok": True, "login": identity["sub"], "username": identity["sub"], "email": identity["email"], "scope": "admin:web",
            "role": identity["role"], "expires_at": identity["expires_at"], "csrf_token": security.keyed("admin-csrf:" + token)}


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    identity = await security.validate_session(request)
    async with async_session() as db:
        await db.execute(security.delete(SecurityRecord).where(SecurityRecord.key == identity["session_key"]))
        await db.commit()
    for cookie in (security.COOKIE, security.DEV_COOKIE, "admin_access_token"):
        response.delete_cookie(cookie, path="/", secure=cookie==security.COOKIE, httponly=True, samesite="strict")
    await _audit(request, identity, reason="session_revoked_logout")
    return {"ok": True}


@router.post("/auth/reauthenticate")
async def reauthenticate(payload: CodePayload, request: Request):
    identity = await security.validate_session(request)
    await security.rate_limit(request, "admin-reauth", identity["owner"], maximum=5)
    async with async_session() as db:
        factor = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == "factor:" + identity["owner"]).with_for_update())
        record = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == identity["session_key"]).with_for_update())
        if not record or record.expires_at <= security.now() or not factor or not await _verify_factor(db, factor, payload.code):
            raise HTTPException(401, "Invalid verification code")
        record.data = {**record.data, "verified_at": security.now()}
        await db.commit()
    await _audit(request, identity, success=True, reason="reauthenticated")
    return {"ok": True}


@router.get("/auth/sessions")
async def sessions(request: Request):
    identity = await security.validate_session(request)
    async with async_session() as db:
        rows = (await db.execute(select(SecurityRecord).where(SecurityRecord.kind == "admin_session", SecurityRecord.expires_at > security.now()))).scalars().all()
    return {"items": [{"id": row.key.split(":", 1)[1], "expires_at": row.expires_at, "current": row.key == identity["session_key"]}
                      for row in rows if row.data.get("owner") == identity["owner"]]}


@router.post("/auth/revoke-all")
async def revoke_all(request: Request, response: Response):
    identity = await security.validate_session(request)
    await security.revoke_owner(identity["owner"])
    for cookie in (security.COOKIE, security.DEV_COOKIE):
        response.delete_cookie(cookie, path="/", secure=cookie==security.COOKIE, httponly=True, samesite="strict")
    await _audit(request, identity, reason="all_sessions_revoked")
    return {"ok": True}


@router.delete("/auth/sessions/{session_id}")
async def revoke_session(session_id: str, request: Request):
    identity = await security.validate_session(request)
    if len(session_id) != 64 or any(c not in "0123456789abcdef" for c in session_id):
        raise HTTPException(404, "Session not found")
    async with async_session() as db:
        record = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == "session:" + session_id).with_for_update())
        if not record or record.kind != "admin_session" or record.data.get("owner") != identity["owner"]:
            raise HTTPException(404, "Session not found")
        await db.delete(record)
        await db.commit()
    await _audit(request, identity, reason="session_revoked_manually")
    return {"ok": True}
