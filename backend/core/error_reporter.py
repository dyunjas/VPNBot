from __future__ import annotations

import asyncio
import html
import logging
import queue
import re
import threading
import traceback
import time

from backend.core.incidents import Event, IncidentBuffer, category, fingerprint, redact, render
from datetime import datetime
from pathlib import Path

import aiohttp
from aiohttp_socks import ProxyConnector


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTER_LOG_PATH = PROJECT_ROOT / "logs" / "error_reporter.log"
TELEGRAM_ID_RE = re.compile(r"(?:tg_id|telegram_user_id|chat_id|user)\s*[=:]\s*(-?\d{5,})", re.IGNORECASE)


def _error_report_settings() -> tuple[str, int, int | None, int, str | None]:
    from backend.core.config import settings

    token = (settings.ERROR_REPORT_BOT_TOKEN or "").strip()
    chat_id = settings.ERROR_REPORT_CHAT_ID
    topic_id = settings.ERROR_REPORT_TOPIC_ID
    max_bytes = settings.ERROR_REPORT_MAX_BYTES
    proxy_url = settings.TELEGRAM_PROXY_URL
    return token, chat_id, topic_id, max_bytes, proxy_url


def _write_reporter_failure(message: str) -> None:
    try:
        REPORTER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REPORTER_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")
    except Exception:
        pass


def _format_exception(record: logging.LogRecord) -> str:
    if record.exc_info:
        return "".join(traceback.format_exception(*record.exc_info)).strip()
    return ""


def _trim_report(text: str, max_bytes: int) -> bytes:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return data
    suffix = "\n\n--- report truncated ---\n".encode("utf-8")
    return data[: max_bytes - len(suffix)].decode("utf-8",errors="ignore").encode("utf-8") + suffix


def _relative_source(pathname: str) -> str:
    path = Path(pathname)
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except Exception:
        return path.as_posix()


def _context_from_path(source: str) -> str:
    if source.startswith("bot/"):
        return "Telegram Bot"
    if source.startswith("api/admin/") or source.startswith("backend/apps/admin_frontend"):
        return "Admin API"
    if source.startswith("api/cabinet/") or source.startswith("backend/apps/cabinet"):
        return "Web Cabinet"
    if source.startswith("api/miniapp/") or source.startswith("backend/apps/miniapp"):
        return "Telegram Mini App"
    if source.startswith("api/bot/"):
        return "Bot Internal API"
    if source.startswith("api/subscription_url/"):
        return "Subscription Webhook"
    if source.startswith("backend/schedulers/"):
        return "Scheduler"
    if source.startswith("backend/services/remnawave") or "remnawave" in source.lower():
        return "Remnawave"
    if source.startswith("backend/payments/") or "payment" in source.lower() or "billing" in source.lower():
        return "Payments"
    if source.startswith("backend/apps/api"):
        return "API"
    if source.startswith("backend/"):
        return "Backend"
    return "Application"


def _record_context(record: logging.LogRecord, source: str) -> str:
    explicit = getattr(record, "app_context", None)
    if explicit:
        return str(explicit)

    base = _context_from_path(source)
    logger_name = record.name or ""
    if logger_name and logger_name != "root":
        return f"{base} / {logger_name}"
    return f"{base} / {source}:{record.lineno}"


def _telegram_user_id(record: logging.LogRecord, message: str) -> str:
    explicit = getattr(record, "telegram_user_id", None)
    if explicit:
        return str(explicit)

    match = TELEGRAM_ID_RE.search(message)
    if match:
        return match.group(1)

    return "-"


class TelegramErrorReportHandler(logging.Handler):
    def __init__(self, *, level=logging.WARNING, start_worker=True):
        super().__init__(level=level)
        self._queue = queue.Queue(maxsize=500)
        self._dropped = 0
        self._drop_lock = threading.Lock()
        self._stopped = False
        self._worker = None
        if start_worker:
            self._worker = threading.Thread(target=self._run,name="telegram-error-reporter",daemon=True)
            self._worker.start()

    def emit(self, record):
        if self._stopped or getattr(record,"telegram_error_report_skip",False): return
        if record.levelno < logging.ERROR and not getattr(record,"security_event",False): return
        try:
            source = _relative_source(record.pathname)
            raw_message = record.getMessage()
            message = redact(raw_message)[:2500]
            user_id = _telegram_user_id(record,raw_message)
            if user_id != "-": message += f"\nTelegram user: {user_id}"
            context = redact(_record_context(record,source))[:300]
            kind = category(record,message)
            # Freeze strings, not LogRecord/traceback objects retaining entire request bodies.
            event = Event(kind,fingerprint(kind,context,source,message),context,
                          f"{source}:{record.lineno}",message,redact(_format_exception(record))[:8000],
                          str(getattr(record,"security_peer",""))[:64],record.created)
            self._queue.put_nowait(event)
        except queue.Full:
            with self._drop_lock: self._dropped += 1
        except Exception as exc:
            _write_reporter_failure(f"cannot prepare report: {type(exc).__name__}")

    def _run(self):
        from backend.core.config import settings
        buffer = IncidentBuffer(window=settings.ERROR_REPORT_BATCH_SECONDS,
                                critical_repeat=settings.ERROR_REPORT_CRITICAL_REPEAT_SECONDS,
                                max_groups=settings.ERROR_REPORT_MAX_GROUPS,now=time.monotonic())
        while True:
            try:
                event = self._queue.get(timeout=1)
            except queue.Empty:
                event = None if self._stopped else False
            try:
                if event is None:
                    pending,overflow = buffer.flush(float("inf"))
                    if pending or overflow: asyncio.run(self._send_report(pending,overflow))
                    return
                if event:
                    immediate = buffer.add(event,time.monotonic())
                    if immediate: asyncio.run(self._send_report(immediate))
                now = time.monotonic()
                due = now >= buffer.next_flush
                pending,overflow = buffer.flush(now)
                if due:
                    with self._drop_lock:
                        overflow += self._dropped
                        self._dropped = 0
                if pending or overflow:
                    asyncio.run(self._send_report(pending,overflow))
            except Exception as exc:
                _write_reporter_failure(f"reporter failure: {type(exc).__name__}")

    async def _send_report(self, incidents, overflow=0):
        token,chat_id,topic_id,max_bytes,proxy = _error_report_settings()
        if not token: return
        summary,report = render(incidents,overflow)
        critical = any(item.event.kind=="critical" for item in incidents)
        form = aiohttp.FormData()
        form.add_field("chat_id",str(chat_id))
        if topic_id: form.add_field("message_thread_id",str(topic_id))
        # Network/security digests are silent; critical alerts use the normal sound.
        form.add_field("disable_notification","false" if critical else "true")
        title,_,body = summary[:900].partition("\n")
        form.add_field("caption",f"<b>{html.escape(title)}</b>\n{html.escape(body)}")
        form.add_field("parse_mode","HTML")
        form.add_field("document",_trim_report(report,max(1024,max_bytes)),
                       filename=f"incidents_{datetime.now():%Y%m%d_%H%M%S}.txt",content_type="text/plain; charset=utf-8")
        connector = ProxyConnector.from_url(proxy) if proxy and proxy.lower().startswith(("socks4://","socks5://")) else None
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10),connector=connector) as session:
                async with session.post(f"https://api.telegram.org/bot{token}/sendDocument",data=form,proxy=None if connector else proxy) as response:
                    result = await response.json(content_type=None)
                    if response.status>=400 or not result.get("ok"):
                        _write_reporter_failure(f"Telegram delivery failed: HTTP {response.status}")
        except Exception as exc:
            # Never log transport exception text: it can contain the bot token URL.
            _write_reporter_failure(f"Telegram delivery failed: {type(exc).__name__}")

    def close(self):
        if not self._stopped:
            self._stopped = True
            try: self._queue.put_nowait(None)
            except queue.Full: pass
        super().close()
