from __future__ import annotations

import json
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


async def _safe_action_details(request: Request) -> tuple[str | None, str | None]:
    try:
        raw = await request.body()
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        return None, None
    if not isinstance(data, dict):
        return None, None
    action = str(data.get("action") or "").strip()
    labels = {
        "add_balance": "Начисление баланса",
        "sub_balance": "Списание баланса",
        "add_traffic": "Начисление трафика",
        "sub_traffic": "Списание трафика",
        "extend_subscription": "Продление подписки",
        "reduce_subscription": "Уменьшение срока подписки",
        "ban": "Блокировка пользователя",
        "unban": "Разблокировка пользователя",
    }
    if action not in labels:
        return None, None
    values = []
    if data.get("amount") is not None:
        values.append(f"{data['amount']} ₽")
    if data.get("gb") is not None:
        values.append(f"{data['gb']} ГБ")
    if data.get("duration_hours") is not None:
        values.append(f"{data['duration_hours']} ч.")
    target = _target_id(request.url.path)
    suffix = f" ({', '.join(values)})" if values else ""
    return labels[action], f"Пользователь #{target}{suffix}" if target else suffix.strip() or None


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
    action, details = await _safe_action_details(request)
    try:
        async with async_session() as session:
            session.add(
                AdminActionLog(
                    admin_id=auth.get("admin_id"),
                    username=(auth.get("sub") or "")[:64] or None,
                    action=action or _action_name(request.method, path),
                    method=request.method,
                    path=path[:255],
                    target_id=_target_id(path),
                    details=details,
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
