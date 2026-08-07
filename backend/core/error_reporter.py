from __future__ import annotations

import asyncio
import html
import logging
import queue
import re
import threading
import traceback
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
    return data[: max_bytes - len(suffix)] + suffix


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
    def __init__(self, *, level: int = logging.ERROR) -> None:
        super().__init__(level=level)
        self._queue: queue.Queue[logging.LogRecord | None] = queue.Queue(maxsize=100)
        self._worker = threading.Thread(target=self._run, name="telegram-error-reporter", daemon=True)
        self._worker.start()

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "telegram_error_report_skip", False):
            return
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            _write_reporter_failure("queue is full; error report skipped")

    def _run(self) -> None:
        while True:
            record = self._queue.get()
            if record is None:
                return
            try:
                asyncio.run(self._send_record(record))
            except Exception as exc:
                _write_reporter_failure(f"unexpected reporter failure: {type(exc).__name__}: {exc}")

    async def _send_record(self, record: logging.LogRecord) -> None:
        token, chat_id, topic_id, max_bytes, proxy = _error_report_settings()
        if not token:
            _write_reporter_failure("ERROR_REPORT_BOT_TOKEN is empty; error report skipped")
            return

        now = datetime.now()
        filename = f"error_report_{now:%Y%m%d_%H%M%S}.txt"
        exc_type = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else record.levelname
        exception_text = _format_exception(record)
        message = record.getMessage()
        source = _relative_source(record.pathname)
        context = _record_context(record, source)
        telegram_user_id = _telegram_user_id(record, message)

        report = (
            "⚠️ Ошибка во время работы\n\n"
            f"Тип: {exc_type}\n"
            "Ошибок в отчёте: 1\n"
            f"Контекст: {context}\n"
            f"Пользователь: {telegram_user_id}\n"
            f"Logger: {record.name}\n"
            f"Источник: {source}:{record.lineno}\n"
            f"Сообщение: {message}\n"
            f"Время: {now:%d.%m.%Y %H:%M:%S}\n"
        )
        if exception_text:
            report += f"\nTraceback:\n{exception_text}\n"

        caption = (
            "⚠️ Ошибка во время работы\n\n"
            f"<b>Тип:</b> <code>{html.escape(exc_type)}</code>\n"
            "<b>Ошибок в отчёте:</b> 1\n"
            f"<b>Контекст:</b> <code>{html.escape(context)}</code>\n"
            f"<b>Пользователь:</b> <code>{html.escape(telegram_user_id)}</code>\n\n"
            f"<i>{now:%d.%m.%Y %H:%M:%S}</i>"
        )

        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        if topic_id:
            form.add_field("message_thread_id", str(topic_id))
        form.add_field("caption", caption)
        form.add_field("parse_mode", "HTML")
        form.add_field(
            "document",
            _trim_report(report, max_bytes),
            filename=filename,
            content_type="text/plain; charset=utf-8",
        )

        url = f"https://api.telegram.org/bot{token}/sendDocument"
        timeout = aiohttp.ClientTimeout(total=30)
        connector = ProxyConnector.from_url(proxy) if proxy and proxy.lower().startswith(("socks4://", "socks5://")) else None
        try:
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                request_proxy = None if connector else proxy
                async with session.post(url, data=form, proxy=request_proxy) as response:
                    body = await response.text()
                    if response.status >= 400:
                        _write_reporter_failure(
                            f"telegram sendDocument failed status={response.status} response={body[:1000]}"
                        )
        except Exception as exc:
            _write_reporter_failure(f"telegram sendDocument request failed: {type(exc).__name__}: {exc}")
