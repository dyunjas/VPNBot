import csv
import io

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from ..common import *
from api.admin.audit import audit_item
from backend.database.models import Admin, AdminActionLog, AdminLoginEvent, AdminRole

router = APIRouter()


class AdminAccessCreatePayload(BaseModel):
    username: str
    email: str
    password: str
    role: AdminRole = AdminRole.support
    is_active: bool = True


class AdminAccessUpdatePayload(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None
    role: AdminRole | None = None
    is_active: bool | None = None


def _admin_access_public(admin: Admin) -> dict:
    return {"id": admin.id, "username": admin.username, "email": admin.email, "role": admin.role.value if hasattr(admin.role, "value") else str(admin.role), "is_active": bool(admin.is_active), "created_at": _to_iso(admin.created_at)}


@router.get("/admins", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_list():
    async with async_session() as session:
        rows = (await session.execute(select(Admin).order_by(desc(Admin.created_at), desc(Admin.id)))).scalars().all()
    return {"ok": True, "roles": [role.value for role in AdminRole], "items": [_admin_access_public(row) for row in rows]}


@router.get("/admins/login-events", dependencies=[Depends(require_superadmin_auth)])
async def admin_login_events(limit: int = Query(default=10, ge=1, le=10), offset: int = Query(default=0, ge=0)):
    async with async_session() as session:
        rows = (
            await session.execute(
                select(AdminLoginEvent)
                .order_by(desc(AdminLoginEvent.created_at), desc(AdminLoginEvent.id))
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
    return {"ok": True, "items": [audit_item(row) for row in rows]}


@router.get("/admins/{admin_id}/audit", dependencies=[Depends(require_superadmin_auth)])
async def admin_audit(admin_id: int, limit: int = Query(default=10, ge=1, le=10)):
    async with async_session() as session:
        admin = await session.get(Admin, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="admin access not found")
        login_rows = (
            await session.execute(
                select(AdminLoginEvent)
                .where(AdminLoginEvent.admin_id == admin_id)
                .order_by(desc(AdminLoginEvent.created_at), desc(AdminLoginEvent.id))
                .limit(limit)
            )
        ).scalars().all()
        action_rows = (
            await session.execute(
                select(AdminActionLog)
                .where(AdminActionLog.admin_id == admin_id)
                .order_by(desc(AdminActionLog.created_at), desc(AdminActionLog.id))
                .limit(limit)
            )
        ).scalars().all()
    return {
        "ok": True,
        "admin": _admin_access_public(admin),
        "login_events": [audit_item(row) for row in login_rows],
        "action_events": [audit_item(row) for row in action_rows],
    }


@router.get("/admins/{admin_id}/audit/download", dependencies=[Depends(require_superadmin_auth)])
async def admin_audit_download(admin_id: int):
    async with async_session() as session:
        admin = await session.get(Admin, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="admin access not found")
        logins = (await session.execute(select(AdminLoginEvent).where(AdminLoginEvent.admin_id == admin_id).order_by(desc(AdminLoginEvent.created_at)))).scalars().all()
        actions = (await session.execute(select(AdminActionLog).where(AdminActionLog.admin_id == admin_id).order_by(desc(AdminActionLog.created_at)))).scalars().all()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["Тип", "Дата", "Администратор", "Результат", "Действие", "Метод", "Путь", "IP", "Причина"])
    for row in logins:
        writer.writerow(["Вход", row.created_at.isoformat() if row.created_at else "", row.username or "", "Успешно" if row.success else "Неуспешно", "", "", "", row.ip_address or "", row.reason or ""])
    for row in actions:
        writer.writerow(["Действие", row.created_at.isoformat() if row.created_at else "", row.username or "", "", row.action, row.method, row.path, row.ip_address or "", row.details or ""])
    return Response(
        content="\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="admin-{admin_id}-audit.csv"'},
    )


@router.post("/admins", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_create(payload: AdminAccessCreatePayload):
    from .auth import hash_admin_password
    username, email, password = payload.username.strip(), payload.email.strip().lower(), payload.password.strip()
    if len(username) < 3 or len(password) < 8 or "@" not in email:
        raise HTTPException(status_code=400, detail="username, valid email and password (8+ chars) are required")
    async with async_session() as session:
        if await session.scalar(select(Admin.id).where(func.lower(Admin.email) == email)):
            raise HTTPException(status_code=409, detail="admin email already exists")
        if await session.scalar(select(Admin.id).where(func.lower(Admin.username) == username.lower())):
            raise HTTPException(status_code=409, detail="admin username already exists")
        admin = Admin(username=username, email=email, password_hash=hash_admin_password(password), role=payload.role, is_active=payload.is_active)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return {"ok": True, "item": _admin_access_public(admin)}


@router.patch("/admins/{admin_id}", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_update(admin_id: int, payload: AdminAccessUpdatePayload):
    from .auth import hash_admin_password
    async with async_session() as session:
        admin = await session.get(Admin, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="admin access not found")
        if payload.username is not None:
            username = payload.username.strip()
            if len(username) < 1:
                raise HTTPException(status_code=400, detail="username must not be empty")
            if await session.scalar(select(Admin.id).where(func.lower(Admin.username) == username.lower(), Admin.id != admin_id)):
                raise HTTPException(status_code=409, detail="admin username already exists")
            admin.username = username
        if payload.email is not None:
            email = payload.email.strip().lower()
            if "@" not in email or await session.scalar(select(Admin.id).where(func.lower(Admin.email) == email, Admin.id != admin_id)):
                raise HTTPException(status_code=409, detail="admin email already exists or is invalid")
            admin.email = email
        if payload.password:
            if len(payload.password.strip()) < 8:
                raise HTTPException(status_code=400, detail="password must be at least 8 characters")
            admin.password_hash = hash_admin_password(payload.password.strip())
        if payload.role is not None:
            admin.role = payload.role
        if payload.is_active is not None:
            admin.is_active = bool(payload.is_active)
        await session.commit()
        await session.refresh(admin)
        return {"ok": True, "item": _admin_access_public(admin)}


@router.delete("/admins/{admin_id}", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_delete(admin_id: int):
    async with async_session() as session:
        admin = await session.get(Admin, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="admin access not found")
        await session.delete(admin)
        await session.commit()
    return {"ok": True}
