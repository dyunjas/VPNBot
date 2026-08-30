from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import Request

from backend.database.models import AdminActionLog, AdminLoginEvent
from backend.database.session import async_session


def _request_meta(request: Request) -> tuple[str | None, str | None]:
    client = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return client, user_agent[:512] if user_agent else None


def _target_id(path: str) -> str | None:
    match = re.search(r"/(\d+)(?:/|$)", path)
    return match.group(1) if match else None


def _action_name(method: str, path: str) -> str:
    parts = [part for part in path.split("/") if part]
    resource = parts[2] if len(parts) > 2 and parts[0] == "api" and parts[1] == "admin" else "админ-панель"
    return f"{method} {resource}"


async def record_login_event(
    request: Request,
    *,
    admin_id: int | None,
    username: str | None,
    email: str | None,
    success: bool,
    reason: str | None = None,
) -> None:
    ip_address, user_agent = _request_meta(request)
    try:
        async with async_session() as session:
            session.add(
                AdminLoginEvent(
                    admin_id=admin_id,
                    username=(username or "")[:64] or None,
                    email=(email or "")[:320] or None,
                    success=success,
                    reason=(reason or "")[:128] or None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            )
            await session.commit()
    except Exception:
        # Аудит не должен ломать авторизацию или рабочее действие администратора.
        return


async def record_admin_action(request: Request, auth: dict) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    path = request.url.path
    if path in {"/api/admin/auth/login", "/api/admin/auth/verify-2fa", "/api/admin/auth/logout"}:
        return
    ip_address, _ = _request_meta(request)
    try:
        async with async_session() as session:
            session.add(
                AdminActionLog(
                    admin_id=auth.get("admin_id"),
                    username=(auth.get("sub") or "")[:64] or None,
                    action=_action_name(request.method, path),
                    method=request.method,
                    path=path[:255],
                    target_id=_target_id(path),
                    ip_address=ip_address,
                )
            )
            await session.commit()
    except Exception:
        return


def audit_item(row) -> dict:
    result = {"id": row.id, "created_at": row.created_at.isoformat() if row.created_at else None}
    if isinstance(row, AdminLoginEvent):
        result.update(
            {
                "admin_id": row.admin_id,
                "username": row.username,
                "email": row.email,
                "success": bool(row.success),
                "reason": row.reason,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
            }
        )
    else:
        result.update(
            {
                "admin_id": row.admin_id,
                "username": row.username,
                "action": row.action,
                "method": row.method,
                "path": row.path,
                "status_code": row.status_code,
                "target_id": row.target_id,
                "details": row.details,
                "ip_address": row.ip_address,
            }
        )
    return result
