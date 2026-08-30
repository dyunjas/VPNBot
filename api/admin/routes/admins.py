from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from ..common import *
from backend.database.models import Admin, AdminRole

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
    return {"ok": True, "roles": [AdminRole.support.value], "items": [_admin_access_public(row) for row in rows]}


@router.post("/admins", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_create(payload: AdminAccessCreatePayload):
    from .auth import hash_admin_password
    username, email, password = payload.username.strip(), payload.email.strip().lower(), payload.password.strip()
    if len(username) < 3 or len(password) < 8 or "@" not in email:
        raise HTTPException(status_code=400, detail="username, valid email and password (8+ chars) are required")
    async with async_session() as session:
        if await session.scalar(select(Admin.id).where(func.lower(Admin.email) == email)):
            raise HTTPException(status_code=409, detail="admin email already exists")
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
