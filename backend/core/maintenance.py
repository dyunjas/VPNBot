from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

MAINTENANCE_MESSAGE = "Сервер не доступен. Идут технические работы."

_STATE_LOCK = Lock()
_STATE_PATH = Path(__file__).resolve().parents[2] / "runtime" / "maintenance_state.json"
_DEFAULT_STATE = {
    "enabled": False,
    "mode": "manual",
    "message": MAINTENANCE_MESSAGE,
    "source": None,
    "updated_at": None,
}


def _ensure_parent_dir() -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _normalize_state(raw: Any) -> dict[str, Any]:
    state = dict(_DEFAULT_STATE)
    if isinstance(raw, dict):
        state.update(raw)
    state["enabled"] = bool(state.get("enabled", False))
    state["mode"] = str(state.get("mode") or "manual").strip().lower() or "manual"
    state["message"] = str(state.get("message") or MAINTENANCE_MESSAGE).strip() or MAINTENANCE_MESSAGE
    source = state.get("source")
    state["source"] = str(source).strip() if source else None
    updated_at = state.get("updated_at")
    state["updated_at"] = str(updated_at).strip() if updated_at else None
    return state


def get_maintenance_state() -> dict[str, Any]:
    with _STATE_LOCK:
        try:
            if not _STATE_PATH.exists():
                return dict(_DEFAULT_STATE)
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return dict(_DEFAULT_STATE)
    return _normalize_state(raw)


def _write_state(state: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_state(state)
    normalized["updated_at"] = datetime.now(timezone.utc).isoformat()
    _ensure_parent_dir()
    with _STATE_LOCK:
        _STATE_PATH.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return normalized


def set_maintenance_state(*, enabled: bool, mode: str = "manual", source: str | None = None, message: str | None = None) -> dict[str, Any]:
    return _write_state(
        {
            "enabled": enabled,
            "mode": mode,
            "source": source,
            "message": message or MAINTENANCE_MESSAGE,
        }
    )


def enable_manual_maintenance(message: str | None = None, source: str | None = "admin") -> dict[str, Any]:
    return set_maintenance_state(enabled=True, mode="manual", source=source, message=message)


def disable_maintenance(source: str | None = "admin") -> dict[str, Any]:
    return set_maintenance_state(enabled=False, mode="manual", source=source, message=MAINTENANCE_MESSAGE)


def enable_auto_maintenance(*, source: str, message: str | None = None) -> dict[str, Any]:
    current = get_maintenance_state()
    if current.get("enabled") and current.get("mode") == "manual":
        return current
    return set_maintenance_state(enabled=True, mode="auto", source=source, message=message)


def is_maintenance_enabled() -> bool:
    return bool(get_maintenance_state().get("enabled", False))


__all__ = [
    "MAINTENANCE_MESSAGE",
    "disable_maintenance",
    "enable_auto_maintenance",
    "enable_manual_maintenance",
    "get_maintenance_state",
    "is_maintenance_enabled",
    "set_maintenance_state",
]
