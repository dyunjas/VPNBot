import asyncio
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.database.session import async_session
from backend.services import RemnaWaveService


def _resolve_msk_timezone():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("Europe/Moscow")
        except ZoneInfoNotFoundError:
            logger.warning("[scheduler][remnawave_sync] tzdata missing, fallback to UTC+03:00")
    return timezone(timedelta(hours=3), name="MSK")


MSK_TZ = _resolve_msk_timezone()


def _parse_sync_times(raw: str) -> list[tuple[int, int]]:
    items: list[tuple[int, int]] = []
    for chunk in (raw or "").split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            hour_str, minute_str = value.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
        except Exception:
            logger.warning("[scheduler][remnawave_sync] invalid time value=%s", value)
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            items.append((hour, minute))
        else:
            logger.warning("[scheduler][remnawave_sync] out-of-range time value=%s", value)
    return items or [(3, 0)]


async def run_remnawave_sync_once() -> None:
    if not settings.REMNAWAVE_AUTO_SYNC_ENABLED:
        return

    async with async_session() as session:
        service = RemnaWaveService(session)
        if not service.enabled:
            logger.warning("[scheduler][remnawave_sync] skipped: remnawave is not configured")
            return
        result = await service.sync_all_local_users()
        logger.info(
            "[scheduler][remnawave_sync] completed total=%s synced=%s failed=%s",
            result["total"],
            result["synced"],
            result["failed"],
        )


async def remnawave_sync_loop(poll_interval_sec: int = 30) -> None:
    executed_keys: set[str] = set()
    schedule = _parse_sync_times(settings.REMNAWAVE_AUTO_SYNC_TIMES)
    logger.info("[scheduler][remnawave_sync] enabled times=%s", ",".join(f"{h:02d}:{m:02d}" for h, m in schedule))

    while True:
        try:
            now_msk = datetime.now(MSK_TZ)
            current_key = now_msk.strftime("%Y-%m-%d %H:%M")
            matching = any(now_msk.hour == hour and now_msk.minute == minute for hour, minute in schedule)
            if matching and current_key not in executed_keys:
                await run_remnawave_sync_once()
                executed_keys.add(current_key)

            current_day = now_msk.strftime("%Y-%m-%d")
            executed_keys = {key for key in executed_keys if key.startswith(current_day)}
        except Exception:
            logger.exception("[scheduler][remnawave_sync] execution error")

        await asyncio.sleep(poll_interval_sec)
