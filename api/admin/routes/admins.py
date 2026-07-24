from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from ..common import *
from backend.database.models import Admin, AdminRole

router = APIRouter()


class AdminAccessCreatePayload(BaseModel):
    user_id: int
    login: str
    password: str
    role: AdminRole = AdminRole.support
    is_active: bool = True


class AdminAccessUpdatePayload(BaseModel):
    login: str | None = None
    password: str | None = None
    role: AdminRole | None = None
    is_active: bool | None = None


def _admin_access_public(admin: Admin) -> dict:
    user = admin.user
    return {
        "id": admin.id,
        "user_id": admin.user_id,
        "login": admin.login,
        "tg_id": user.tg_id if user else None,
        "username": user.username if user else None,
        "role": admin.role.value if hasattr(admin.role, "value") else str(admin.role),
        "is_active": bool(admin.is_active),
        "created_at": _to_iso(admin.created_at),
    }


@router.get("/admins", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_list():
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Admin)
                .options(selectinload(Admin.user))
                .join(User, User.id == Admin.user_id)
                .order_by(desc(Admin.created_at), desc(Admin.id))
            )
        ).scalars().all()
    return {
        "ok": True,
        "roles": [AdminRole.support.value],
        "items": [_admin_access_public(row) for row in rows],
    }


@router.post("/admins", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_create(payload: AdminAccessCreatePayload):
    async with async_session() as session:
        from .auth import hash_admin_password

        user = await session.get(User, payload.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        if payload.role != AdminRole.support:
            raise HTTPException(status_code=400, detail="only support role can be granted")

        login = payload.login.strip()
        password = payload.password.strip()
        if len(login) < 3:
            raise HTTPException(status_code=400, detail="login must be at least 3 characters")
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="password must be at least 8 characters")

        existing = (
            await session.execute(select(Admin).where(Admin.user_id == payload.user_id))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="admin access already exists")

        existing_login = (
            await session.execute(select(Admin).where(func.lower(Admin.login) == login.lower()))
        ).scalar_one_or_none()
        if existing_login:
            raise HTTPException(status_code=409, detail="admin login already exists")

        admin = Admin(
            user_id=payload.user_id,
            login=login,
            password_hash=hash_admin_password(password),
            role=payload.role,
            is_active=payload.is_active,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        await session.refresh(admin, attribute_names=["user"])
        return {"ok": True, "item": _admin_access_public(admin)}


@router.patch("/admins/{admin_id}", dependencies=[Depends(require_superadmin_auth)])
async def admin_access_update(admin_id: int, payload: AdminAccessUpdatePayload):
    async with async_session() as session:
        from .auth import hash_admin_password

        admin = await session.get(Admin, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="admin access not found")
        if payload.login is not None:
            login = payload.login.strip()
            if len(login) < 3:
                raise HTTPException(status_code=400, detail="login must be at least 3 characters")
            existing_login = (
                await session.execute(
                    select(Admin).where(
                        func.lower(Admin.login) == login.lower(),
                        Admin.id != admin_id,
                    )
                )
            ).scalar_one_or_none()
            if existing_login:
                raise HTTPException(status_code=409, detail="admin login already exists")
            admin.login = login
        if payload.password is not None:
            password = payload.password.strip()
            if password:
                if len(password) < 8:
                    raise HTTPException(status_code=400, detail="password must be at least 8 characters")
                admin.password_hash = hash_admin_password(password)
        if payload.role is not None:
            if payload.role != AdminRole.support:
                raise HTTPException(status_code=400, detail="only support role can be granted")
            admin.role = payload.role
        if payload.is_active is not None:
            admin.is_active = bool(payload.is_active)
        await session.commit()
        await session.refresh(admin)
        await session.refresh(admin, attribute_names=["user"])
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
