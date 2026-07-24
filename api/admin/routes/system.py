from __future__ import annotations

import os
import platform
import shutil
import socket
import time

from aiogram import Bot
from aiogram.types import LabeledPrice
from sqlalchemy import text

try:
    import psutil
except ImportError:  # pragma: no cover - runtime fallback for incomplete installs
    psutil = None

from ..common import *
from backend.core.loader import bot as runtime_bot
from backend.core.logger_config import logger
from backend.core.business_config import list_business_settings, update_business_settings
from backend.core.maintenance import (
    MAINTENANCE_MESSAGE,
    disable_maintenance,
    enable_manual_maintenance,
    get_maintenance_state,
)
from backend.core.telegram import create_telegram_session

router = APIRouter()


class MaintenanceUpdatePayload(BaseModel):
    enabled: bool
    message: str | None = None


class StarsInvoicePayload(BaseModel):
    amount: int = Field(gt=0, le=100000)


class BusinessSettingsPayload(BaseModel):
    values: dict[str, str | int | float]


def _health_item(
    key: str,
    label: str,
    status: str,
    message: str,
    *,
    latency_ms: int | None = None,
    checked_at: datetime | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "message": message,
        "latency_ms": latency_ms,
        "checked_at": _to_iso(checked_at or datetime.now(timezone.utc)),
        "details": details or {},
    }


async def _timed_check(key: str, label: str, checker):
    started = time.perf_counter()
    checked_at = datetime.now(timezone.utc)
    try:
        status, message, details = await asyncio.wait_for(checker(), timeout=4)
    except asyncio.TimeoutError:
        return _health_item(key, label, "danger", "Проверка превысила 4 секунды", checked_at=checked_at)
    except Exception as exc:
        logger.warning("[admin][health] check failed key=%s err=%s", key, exc)
        return _health_item(key, label, "danger", str(exc), checked_at=checked_at)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return _health_item(
        key,
        label,
        status,
        message,
        latency_ms=latency_ms,
        checked_at=checked_at,
        details=details if isinstance(details, dict) else {},
    )


async def _check_api():
    return "ok", "API отвечает", {"service": "api"}


async def _check_database():
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    return "ok", "База данных отвечает", {}




def _bytes_to_gb(value: int | float | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / (1024**3), 2)


def _format_uptime(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
def _metric_status(percent: float | None, *, warn: float = 70, danger: float = 90) -> str:
    if percent is None:
        return "warn"
    if percent >= danger:
        return "danger"
    if percent >= warn:
        return "warn"
    return "ok"
def _windows_filetime_to_int(filetime) -> int:
    return (int(filetime.dwHighDateTime) << 32) + int(filetime.dwLowDateTime)


def _windows_cpu_percent(interval: float = 0.15) -> float | None:
    if platform.system().lower() != "windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        idle1 = wintypes.FILETIME()
        kernel1 = wintypes.FILETIME()
        user1 = wintypes.FILETIME()
        idle2 = wintypes.FILETIME()
        kernel2 = wintypes.FILETIME()
        user2 = wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle1), ctypes.byref(kernel1), ctypes.byref(user1)):
            return None
        time.sleep(interval)
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle2), ctypes.byref(kernel2), ctypes.byref(user2)):
            return None
        idle = _windows_filetime_to_int(idle2) - _windows_filetime_to_int(idle1)
        kernel = _windows_filetime_to_int(kernel2) - _windows_filetime_to_int(kernel1)
        user = _windows_filetime_to_int(user2) - _windows_filetime_to_int(user1)
        total = kernel + user
        if total <= 0:
            return None
        return round(max(0.0, min(100.0, (total - idle) * 100.0 / total)), 1)
    except Exception:
        return None


def _windows_memory() -> dict | None:
    if platform.system().lower() != "windows":
        return None
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None
        used = int(stat.ullTotalPhys - stat.ullAvailPhys)
        return {
            "percent": float(stat.dwMemoryLoad),
            "used": used,
            "total": int(stat.ullTotalPhys),
            "available": int(stat.ullAvailPhys),
        }
    except Exception:
        return None


def _fallback_process_memory() -> dict:
    if platform.system().lower() == "windows":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return {"rss": int(counters.WorkingSetSize), "vms": int(counters.PagefileUsage)}
        except Exception:
            pass
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as file:
            parts = file.read().split()
        page_size = os.sysconf("SC_PAGE_SIZE")
        return {"rss": int(parts[1]) * page_size, "vms": int(parts[0]) * page_size}
    except Exception:
        return {"rss": None, "vms": None}


def _collect_server_load_fallback() -> dict:
    checked_at = datetime.now(timezone.utc)
    cpu_percent = _windows_cpu_percent()
    memory = _windows_memory()
    disk = shutil.disk_usage(os.getcwd())
    disk_percent = 0.0 if disk.total <= 0 else round((disk.used / disk.total) * 100, 1)
    process_memory = _fallback_process_memory()
    process_percent = 0.0
    if memory and memory.get("total") and process_memory.get("rss"):
        process_percent = round((float(process_memory["rss"]) / float(memory["total"])) * 100, 2)
    load_average = os.getloadavg() if hasattr(os, "getloadavg") else None

    metrics = [
        {
            "key": "cpu",
            "label": "CPU",
            "percent": cpu_percent,
            "value": f"{cpu_percent:.1f}%" if cpu_percent is not None else "n/a",
            "status": _metric_status(cpu_percent),
            "details": {"logical_cores": os.cpu_count(), "load_average": load_average, "source": "stdlib"},
        },
        {
            "key": "memory",
            "label": "RAM",
            "percent": round(memory["percent"], 1) if memory else None,
            "value": f"{memory['percent']:.1f}%" if memory else "n/a",
            "status": _metric_status(float(memory["percent"]) if memory else None),
            "details": {
                "used_gb": _bytes_to_gb(memory["used"] if memory else None),
                "total_gb": _bytes_to_gb(memory["total"] if memory else None),
                "available_gb": _bytes_to_gb(memory["available"] if memory else None),
                "source": "stdlib",
            },
        },
        {
            "key": "disk",
            "label": "Disk",
            "percent": disk_percent,
            "value": f"{disk_percent:.1f}%",
            "status": _metric_status(disk_percent, warn=75, danger=90),
            "details": {
                "path": os.getcwd(),
                "used_gb": _bytes_to_gb(disk.used),
                "total_gb": _bytes_to_gb(disk.total),
                "free_gb": _bytes_to_gb(disk.free),
                "source": "stdlib",
            },
        },
        {
            "key": "process_memory",
            "label": "API process",
            "percent": process_percent,
            "value": f"{_bytes_to_gb(process_memory['rss'])} GB RSS" if process_memory.get("rss") else "n/a",
            "status": _metric_status(process_percent, warn=15, danger=30),
            "details": {
                "pid": os.getpid(),
                "rss_gb": _bytes_to_gb(process_memory.get("rss")),
                "vms_gb": _bytes_to_gb(process_memory.get("vms")),
                "source": "stdlib",
            },
        },
    ]
    return {
        "ok": True,
        "checked_at": _to_iso(checked_at),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "metrics_available": True,
        "metrics_source": "stdlib",
        "metrics": metrics,
        "summary": {
            "uptime": "—",
            "load_average": load_average,
            "cpu_count": os.cpu_count(),
        },
    }

def _collect_server_load() -> dict:
    checked_at = datetime.now(timezone.utc)
    result = {
        "ok": True,
        "checked_at": _to_iso(checked_at),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "metrics_available": psutil is not None,
        "metrics": [],
        "summary": {},
    }
    if psutil is None:
        return _collect_server_load_fallback()

    process = psutil.Process(os.getpid())
    cpu_percent = float(psutil.cpu_percent(interval=0.15))
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())
    process_memory = process.memory_info()
    process_percent = float(process.memory_percent())
    boot_time = float(psutil.boot_time())
    load_average = os.getloadavg() if hasattr(os, "getloadavg") else None
    cpu_freq = psutil.cpu_freq()

    result["metrics"] = [
        {
            "key": "cpu",
            "label": "CPU",
            "percent": round(cpu_percent, 1),
            "value": f"{cpu_percent:.1f}%",
            "status": _metric_status(cpu_percent),
            "details": {
                "logical_cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
                "frequency_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
                "load_average": load_average,
            },
        },
        {
            "key": "memory",
            "label": "RAM",
            "percent": round(float(memory.percent), 1),
            "value": f"{memory.percent:.1f}%",
            "status": _metric_status(float(memory.percent)),
            "details": {
                "used_gb": _bytes_to_gb(memory.used),
                "total_gb": _bytes_to_gb(memory.total),
                "available_gb": _bytes_to_gb(memory.available),
            },
        },
        {
            "key": "disk",
            "label": "Disk",
            "percent": round(float(disk.percent), 1),
            "value": f"{disk.percent:.1f}%",
            "status": _metric_status(float(disk.percent), warn=75, danger=90),
            "details": {
                "path": os.getcwd(),
                "used_gb": _bytes_to_gb(disk.used),
                "total_gb": _bytes_to_gb(disk.total),
                "free_gb": _bytes_to_gb(disk.free),
            },
        },
        {
            "key": "process_memory",
            "label": "API process",
            "percent": round(process_percent, 2),
            "value": f"{_bytes_to_gb(process_memory.rss)} GB RSS",
            "status": _metric_status(process_percent, warn=15, danger=30),
            "details": {
                "pid": process.pid,
                "rss_gb": _bytes_to_gb(process_memory.rss),
                "vms_gb": _bytes_to_gb(process_memory.vms),
                "threads": process.num_threads(),
            },
        },
    ]
    result["summary"] = {
        "uptime_seconds": int(time.time() - boot_time),
        "uptime": _format_uptime(time.time() - boot_time),
        "boot_time": _to_iso(datetime.fromtimestamp(boot_time, timezone.utc)),
        "load_average": load_average,
        "cpu_count": psutil.cpu_count(logical=True),
    }
    return result

@router.get("/system/maintenance", dependencies=[Depends(require_superadmin_auth)])
async def admin_system_maintenance_state():
    state = get_maintenance_state()
    return {"ok": True, "maintenance": state}


@router.post("/system/maintenance", dependencies=[Depends(require_superadmin_auth)])
async def admin_system_maintenance_update(payload: MaintenanceUpdatePayload):
    if payload.enabled:
        state = enable_manual_maintenance(message=(payload.message or MAINTENANCE_MESSAGE), source="admin")
    else:
        state = disable_maintenance(source="admin")
    return {"ok": True, "maintenance": state}


@router.post("/system/stars-invoice", dependencies=[Depends(require_superadmin_auth)])
async def admin_system_stars_invoice(payload: StarsInvoicePayload):
    amount = int(payload.amount or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    bot_instance = runtime_bot
    temp_bot: Bot | None = None
    if bot_instance is None:
        bot_token = (settings.BOT_TOKEN or "").strip()
        if not bot_token:
            raise HTTPException(status_code=503, detail="BOT_TOKEN is not configured")
        temp_bot = Bot(token=bot_token, session=create_telegram_session())
        bot_instance = temp_bot

    invoice_payload = f"admin_stars_topup:{uuid.uuid4().hex}:{amount}"
    try:
        invoice_url = await bot_instance.create_invoice_link(
            title="Пополнение баланса бота",
            description=f"Пополнение баланса Telegram Stars бота на {amount} ⭐",
            payload=invoice_payload,
            currency="XTR",
            prices=[LabeledPrice(label="Telegram Stars", amount=amount)],
            provider_token="",
        )
    except Exception as exc:
        logger.exception("[admin][system] stars invoice creation failed amount=%s", amount)
        raise HTTPException(status_code=502, detail=f"failed to create Stars invoice: {exc}")
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()

    return {
        "ok": True,
        "amount": amount,
        "currency": "XTR",
        "invoice_url": invoice_url,
        "payload": invoice_payload,
    }


@router.get("/system/business-settings", dependencies=[Depends(require_superadmin_auth)])
async def admin_system_business_settings():
    return {"ok": True, "items": list_business_settings()}


@router.put("/system/business-settings", dependencies=[Depends(require_superadmin_auth)])
async def admin_system_business_settings_update(payload: BusinessSettingsPayload):
    try:
        items = update_business_settings(payload.values)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"unknown setting: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "items": items}


@router.get("/system/health", dependencies=[Depends(require_superadmin_auth)])
async def admin_system_health():
    checks = await asyncio.gather(
        _timed_check("api", "API", _check_api),
        _timed_check("database", "БД", _check_database),
    )
    rank = {"ok": 0, "warn": 1, "danger": 2}
    overall = max((item["status"] for item in checks), key=lambda status: rank.get(status, 2), default="ok")
    return {
        "ok": True,
        "overall": overall,
        "checked_at": _to_iso(datetime.now(timezone.utc)),
        "items": checks,
    }


@router.get("/system/server-load", dependencies=[Depends(require_superadmin_auth)])
async def admin_system_server_load():
    return await asyncio.to_thread(_collect_server_load)
