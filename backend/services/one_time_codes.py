"""Hashed, shared, single-use email/Telegram login challenges."""
import hashlib
import hmac
import time

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.database.models import SecurityRecord, SecurityRateBucket
from backend.database.session import async_session
from backend.services.admin_security import keyed


def key(channel, identity):
    return hashlib.sha256((channel + ":" + identity.strip().lower()).encode()).hexdigest()


async def put(channel, identity, user_id, code):
    record_key = "otp:" + key(channel, identity)
    async with async_session() as db:
        insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
        values = dict(key=record_key, kind="login_otp", expires_at=int(time.time()) + 600,
                      data={"user_id": user_id, "code_hash": keyed(record_key + ":" + code), "attempts": 0})
        await db.execute(insert(SecurityRecord).values(**values).on_conflict_do_update(index_elements=[SecurityRecord.key], set_={"data": values["data"], "expires_at": values["expires_at"]}))
        await db.commit()


async def allowed(channel, identity, *, cooldown_sec=None, window_sec=None, max_sends=None):
    timestamp = int(time.time())
    cooldown = int(cooldown_sec or 30)
    window = int(window_sec or 3600)
    maximum = int(max_sends or 10)
    async with async_session() as db:
        insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
        cooldown_key = "otp-cooldown:" + key(channel, identity)
        reservation = await db.scalar(insert(SecurityRecord).values(key=cooldown_key, kind="otp_cooldown", data={}, expires_at=timestamp + cooldown)
            .on_conflict_do_update(index_elements=[SecurityRecord.key], set_={"expires_at": timestamp + cooldown}, where=SecurityRecord.expires_at <= timestamp)
            .returning(SecurityRecord.key))
        if not reservation:
            await db.rollback()
            return False
        bucket = hashlib.sha256(("otp-send:" + key(channel, identity) + ":" + str(timestamp // window)).encode()).hexdigest()
        count = await db.scalar(insert(SecurityRateBucket).values(key=bucket, count=1, expires_at=(timestamp // window + 1) * window)
            .on_conflict_do_update(index_elements=[SecurityRateBucket.key], set_={"count": SecurityRateBucket.count + 1}).returning(SecurityRateBucket.count))
        await db.commit()
        return count <= maximum


async def retry_after(channel, identity, **options):
    async with async_session() as db:
        record = await db.get(SecurityRecord, "otp-cooldown:" + key(channel, identity))
        return max(1, record.expires_at - int(time.time())) if record else 60


async def consume(channel, identity, code, *, max_attempts=5):
    record_key = "otp:" + key(channel, identity)
    async with async_session() as db:
        record = await db.scalar(select(SecurityRecord).where(SecurityRecord.key == record_key).with_for_update())
        if not record or record.expires_at <= int(time.time()) or record.kind != "login_otp":
            return False, None
        old = dict(record.data)
        matched = hmac.compare_digest(old.get("code_hash", ""), keyed(record_key + ":" + str(code).strip()))
        if matched or int(old.get("attempts", 0)) + 1 >= max_attempts:
            removed = await db.scalar(delete(SecurityRecord).where(SecurityRecord.key == record_key, SecurityRecord.data == old).returning(SecurityRecord.key))
            await db.commit()
            return (True, old.get("user_id")) if matched and removed else (False, None)
        await db.scalar(update(SecurityRecord).where(SecurityRecord.key == record_key, SecurityRecord.data == old)
            .values(data={**old, "attempts": int(old.get("attempts", 0)) + 1}).returning(SecurityRecord.key))
        await db.commit()
        return False, None


async def pop(channel, identity, code):
    matched, user_id = await consume(channel, identity, code)
    return user_id if matched else None
