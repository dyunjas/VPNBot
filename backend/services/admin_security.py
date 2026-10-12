"""Admin credentials, persistent revocable sessions and TOTP (RFC 6238).

Uses the existing transactional database instead of introducing a mandatory Redis service.
No administrative JWT is accepted. All records survive worker/application restarts.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
import asyncio
import urllib.request
from urllib.parse import urlparse

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.core.config import settings
from backend.database.models import Admin, SecurityRecord, SecurityRateBucket
from backend.database.session import async_session

SESSION_TTL = 43200
CHALLENGE_TTL = 600
FRESH_TTL = 300
COOKIE = "__Host-lunet_admin"
DEV_COOKIE = "lunet_admin_dev"
CSRF_HEADER = "X-Admin-CSRF"
PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)
_DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def now() -> int:
    return int(time.time())


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def keyed(value: str) -> str:
    secret = (settings.SECRET_KEY or "").strip()
    if len(secret) < 32:
        raise HTTPException(503, "Security configuration is incomplete")
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def cipher() -> Fernet:
    # Independent, versioned domain; changing SECRET_KEY invalidates sessions and factors.
    material = bytes.fromhex(keyed("lunet:admin:totp-encryption:v1"))
    return Fernet(base64.urlsafe_b64encode(material))


def hash_password(password: str) -> str:
    return PASSWORDS.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    if encoded and encoded.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = encoded.split("$", 3)
            rounds = int(iterations)
            if not 10000 <= rounds <= 2000000:
                return False
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), rounds).hex()
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    try:
        return PASSWORDS.verify(encoded or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError, TypeError):
        return False


def password_policy(password: str) -> None:
    # Offline deny-list; no plaintext passwords sent to an external service.
    common = {"password", "password123", "password123!", "admin123456789", "qwerty123456789", "123456789012"}
    if not 12 <= len(password) <= 256 or password.lower() in common or len(set(password)) < 5:
        raise HTTPException(400, "Choose a stronger password (12–256 characters)")


async def check_compromised_password(password: str) -> None:
    password_policy(password)
    fingerprint = hashlib.sha1(password.encode()).hexdigest().upper()
    def lookup():
        request = urllib.request.Request("https://api.pwnedpasswords.com/range/" + fingerprint[:5], headers={"Add-Padding": "true", "User-Agent": "Lunet-Password-Policy"})
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.read(1024 * 1024).decode("ascii")
    try:
        rows = await asyncio.to_thread(lookup)
        for row in rows.splitlines():
            suffix, count = row.strip().split(":", 1)
            if hmac.compare_digest(suffix, fingerprint[5:]) and int(count) > 0:
                raise HTTPException(400, "This password appears in a breach. Choose another password")
    except HTTPException:
        raise
    except Exception:
        # No silent bypass of the breach check when setting administrative credentials.
        raise HTTPException(503, "Password safety check is temporarily unavailable")


def totp(secret: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 15
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7fffffff
    return str(value % (10 ** digits)).zfill(digits)


def accepted_counter(secret: str, code: str, last: int = -1) -> int | None:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    current = now() // 30
    for counter in (current, current - 1, current + 1):
        if counter > last and hmac.compare_digest(totp(secret, counter), code):
            return counter
    return None


def local_http(request: Request) -> bool:
    origin = urlparse(request.headers.get("origin") or str(request.base_url))
    return (request.url.scheme == "http" and origin.scheme == "http"
            and origin.hostname in {"localhost", "127.0.0.1", "::1"}
            and request.client is not None and request.client.host in {"127.0.0.1", "::1", "testclient"})


def check_origin(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    allowed = set(settings.API_CORS_ORIGINS_LIST)
    allowed.add(str(request.base_url).rstrip("/"))
    public = urlparse(str(settings.PUBLIC_BASE_URL or ""))
    if public.scheme and public.netloc:
        allowed.add(f"{public.scheme}://{public.netloc}")
    if not origin or (origin not in allowed and not local_http(request)):
        raise HTTPException(403, "Request origin is not allowed")
    if not local_http(request) and request.url.scheme != "https":
        raise HTTPException(403, "HTTPS is required")


async def rate_limit(request: Request, operation: str, account: str = "", maximum: int = 10, window: int = 300) -> None:
    stamp = now()
    address = request.client.host if request.client else "unknown"
    # Separate account and IP buckets prevent simple login-name rotation.
    subjects = [(f"ip:{address}", maximum * 4)]
    if account:
        subjects.append((f"account:{account.lower()}", maximum))
    async with async_session() as db:
        exceeded = False
        for subject, limit in subjects:
            key = digest(f"{operation}:{subject}:{stamp // window}")
            insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
            statement = insert(SecurityRateBucket).values(key=key, count=1, expires_at=stamp + window * 2)
            statement = statement.on_conflict_do_update(index_elements=[SecurityRateBucket.key], set_={"count": SecurityRateBucket.count + 1}).returning(SecurityRateBucket.count)
            exceeded = int(await db.scalar(statement)) > limit or exceeded
        await db.execute(delete(SecurityRateBucket).where(SecurityRateBucket.expires_at < stamp))
        await db.commit()
    if exceeded:
        raise HTTPException(429, "Too many attempts. Try again later", headers={"Retry-After": str(window)})


async def principal(db, owner: str) -> dict | None:
    if owner.startswith("admin:"):
        try:
            admin = await db.get(Admin, int(owner.split(":", 1)[1]))
        except ValueError:
            return None
        if not admin or not admin.is_active:
            return None
        role = admin.role.value if hasattr(admin.role, "value") else str(admin.role)
        if role not in {"superadmin", "support"}:
            return None
        return {"owner": owner, "sub": admin.username, "email": admin.email, "admin_id": admin.id, "role": role,
                "fingerprint": keyed(f"admin:{admin.id}:{admin.email}:{admin.password_hash}:{role}:{admin.is_active}")}
    login = (settings.ADMIN_WEB_EMAIL or settings.ADMIN_WEB_LOGIN or "").strip().lower()
    password = settings.ADMIN_WEB_PASSWORD or ""
    if not login or not password or owner != "master:" + digest(login):
        return None
    return {"owner": owner, "sub": login, "email": settings.ADMIN_WEB_EMAIL, "admin_id": None, "role": "superadmin",
            "fingerprint": keyed(f"master:{login}:{password}")}


async def create_session(db, identity: dict, factor: SecurityRecord) -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    csrf = keyed("admin-csrf:" + token)
    db.add(SecurityRecord(key="session:" + digest(token), kind="admin_session", expires_at=now() + SESSION_TTL,
                          data={"owner": identity["owner"], "fingerprint": identity["fingerprint"], "factor_version": factor.data["version"],
                                "verified_at": now(), "csrf_hash": digest(csrf), "two_factor": True}))
    return token, csrf


async def validate_session(request: Request) -> dict:
    if getattr(request.state, "admin_auth", None):
        return request.state.admin_auth
    token = request.cookies.get(COOKIE) or (request.cookies.get(DEV_COOKIE) if local_http(request) else None)
    if not token or len(token) > 128:
        raise HTTPException(401, "Unauthorized")
    async with async_session() as db:
        record = await db.get(SecurityRecord, "session:" + digest(token))
        if not record or record.kind != "admin_session" or record.expires_at <= now() or not record.data.get("two_factor"):
            raise HTTPException(401, "Unauthorized")
        identity = await principal(db, record.data.get("owner", ""))
        factor = await db.get(SecurityRecord, "factor:" + record.data.get("owner", ""))
        if not identity or not factor or identity["fingerprint"] != record.data.get("fingerprint") or factor.data.get("version") != record.data.get("factor_version"):
            raise HTTPException(401, "Unauthorized")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            check_origin(request)
            csrf = request.headers.get(CSRF_HEADER, "")
            if not csrf or not hmac.compare_digest(digest(csrf), record.data.get("csrf_hash", "")):
                raise HTTPException(403, "Invalid CSRF token")
        identity.update(scope="admin:web", session_key=record.key, verified_at=record.data.get("verified_at", 0), expires_at=record.expires_at)
    request.state.admin_auth = identity
    return identity


def require_fresh(identity: dict) -> None:
    if now() - int(identity.get("verified_at", 0)) >= FRESH_TTL:
        raise HTTPException(403, {"code": "admin_reauthentication_required", "message": "Confirm your authenticator code to continue"})


def set_session_cookie(response, request, token: str) -> None:
    response.set_cookie(DEV_COOKIE if local_http(request) else COOKIE, token, max_age=SESSION_TTL,
                        httponly=True, secure=not local_http(request), samesite="strict", path="/")


async def revoke_owner(owner: str) -> None:
    async with async_session() as db:
        # Authorization also checks current credentials/role on every request, before deletion.
        rows = (await db.execute(select(SecurityRecord).where(SecurityRecord.kind == "admin_session"))).scalars().all()
        for row in rows:
            if row.data.get("owner") == owner:
                await db.delete(row)
        await db.commit()
