from fastapi import APIRouter
from ..common import *
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from backend.core import loader as bot_loader
from backend.core.logger_config import logger

router = APIRouter()

BROADCAST_JOBS: dict[str, dict] = {}
BROADCAST_JOBS_LOCK = asyncio.Lock()
BROADCAST_KEEP_HOURS = 12
BROADCAST_SEND_TIMEOUT_SEC = 12


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _job_public(job: dict) -> dict:
    started_at = job.get("started_at")
    finished_at = job.get("finished_at")
    elapsed = None
    if isinstance(started_at, datetime):
        end_dt = finished_at if isinstance(finished_at, datetime) else _utc_now()
        elapsed = max(0, int((end_dt - started_at).total_seconds()))

    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "total": int(job.get("total") or 0),
        "processed": int(job.get("processed") or 0),
        "success": int(job.get("success") or 0),
        "failed": int(job.get("failed") or 0),
        "failed_samples": list(job.get("failed_samples") or []),
        "error": job.get("error"),
        "created_at": _to_iso(job.get("created_at")),
        "started_at": _to_iso(started_at),
        "finished_at": _to_iso(finished_at),
        "elapsed_seconds": elapsed,
    }


async def _resolve_broadcast_bot() -> tuple[Bot, Bot | None]:
    runtime_bot = bot_loader.bot
    if runtime_bot is not None:
        return runtime_bot, None

    bot_token = (settings.BOT_TOKEN or "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not configured")

    proxy_url = (settings.BOT_PROXY or "").strip() or None
    session = AiohttpSession(proxy=proxy_url) if proxy_url else AiohttpSession()
    temp_bot = Bot(token=bot_token, session=session)
    return temp_bot, temp_bot


async def _cleanup_jobs() -> None:
    cutoff = _utc_now() - timedelta(hours=BROADCAST_KEEP_HOURS)
    async with BROADCAST_JOBS_LOCK:
        stale_ids = []
        for jid, job in BROADCAST_JOBS.items():
            created_at = job.get("created_at")
            if isinstance(created_at, datetime) and created_at < cutoff:
                stale_ids.append(jid)
        for jid in stale_ids:
            BROADCAST_JOBS.pop(jid, None)


async def _run_broadcast_job(
    job_id: str,
    text: str,
    parse_mode: Literal["HTML", "MarkdownV2"],
    include_banned: bool,
    image_bytes: bytes | None,
    image_name: str,
) -> None:
    async with BROADCAST_JOBS_LOCK:
        job = BROADCAST_JOBS.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["started_at"] = _utc_now()

    try:
        runtime_bot, temp_bot = await _resolve_broadcast_bot()

        try:
            async with async_session() as session:
                query = select(User.tg_id).where(User.tg_id.is_not(None))
                if not include_banned:
                    query = query.where(User.banned.is_(False))
                user_tg_ids = [int(row[0]) for row in (await session.execute(query)).all()]

            total = len(user_tg_ids)
            success = 0
            failed = 0
            failed_samples: list[dict] = []

            async with BROADCAST_JOBS_LOCK:
                job = BROADCAST_JOBS.get(job_id)
                if not job:
                    return
                job["total"] = total

            if total == 0:
                async with BROADCAST_JOBS_LOCK:
                    job = BROADCAST_JOBS.get(job_id)
                    if not job:
                        return
                    job["status"] = "completed"
                    job["processed"] = 0
                    job["success"] = 0
                    job["failed"] = 0
                    job["finished_at"] = _utc_now()
                return

            for idx, tg_id in enumerate(user_tg_ids, start=1):
                try:
                    if image_bytes:
                        photo = BufferedInputFile(image_bytes, filename=image_name)
                        await asyncio.wait_for(
                            runtime_bot.send_photo(chat_id=tg_id, photo=photo, caption=text, parse_mode=parse_mode),
                            timeout=BROADCAST_SEND_TIMEOUT_SEC,
                        )
                    else:
                        await asyncio.wait_for(
                            runtime_bot.send_message(chat_id=tg_id, text=text, parse_mode=parse_mode),
                            timeout=BROADCAST_SEND_TIMEOUT_SEC,
                        )
                    success += 1
                except asyncio.TimeoutError:
                    failed += 1
                    if len(failed_samples) < 30:
                        failed_samples.append({"tg_id": tg_id, "error": "timeout while sending"})
                except Exception as exc:
                    failed += 1
                    if len(failed_samples) < 30:
                        failed_samples.append({"tg_id": tg_id, "error": str(exc)[:140]})
                    logger.warning("[admin][broadcast] send failed tg_id=%s error=%s", tg_id, str(exc)[:200])
                finally:
                    async with BROADCAST_JOBS_LOCK:
                        job = BROADCAST_JOBS.get(job_id)
                        if not job:
                            return
                        job["processed"] = idx
                        job["success"] = success
                        job["failed"] = failed
                        job["failed_samples"] = list(failed_samples)
                    await asyncio.sleep(0.05)

            async with BROADCAST_JOBS_LOCK:
                job = BROADCAST_JOBS.get(job_id)
                if not job:
                    return
                job["status"] = "completed"
                job["processed"] = total
                job["success"] = success
                job["failed"] = failed
                job["failed_samples"] = list(failed_samples)
                job["finished_at"] = _utc_now()
        finally:
            if temp_bot is not None:
                await temp_bot.session.close()
    except Exception as exc:
        async with BROADCAST_JOBS_LOCK:
            job = BROADCAST_JOBS.get(job_id)
            if not job:
                return
            job["status"] = "failed"
            job["error"] = str(exc)
            job["finished_at"] = _utc_now()


@router.post("/broadcast/upload", dependencies=[Depends(require_admin_auth)])
async def admin_broadcast_upload(
    text: str = Form(...),
    parse_mode: Literal["HTML", "MarkdownV2"] = Form("HTML"),
    include_banned: bool = Form(False),
    image: UploadFile | None = File(default=None),
):
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    image_bytes: bytes | None = None
    image_name = "broadcast.jpg"
    if image is not None:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="image is empty")
        image_name = image.filename or image_name

    await _cleanup_jobs()
    job_id = uuid.uuid4().hex
    async with BROADCAST_JOBS_LOCK:
        BROADCAST_JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "total": 0,
            "processed": 0,
            "success": 0,
            "failed": 0,
            "failed_samples": [],
            "error": None,
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
        }

    asyncio.create_task(
        _run_broadcast_job(
            job_id=job_id,
            text=text,
            parse_mode=parse_mode,
            include_banned=include_banned,
            image_bytes=image_bytes,
            image_name=image_name,
        )
    )

    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/admin-api/broadcast/jobs/{job_id}",
        "premium_emoji_note": "Use HTML with <tg-emoji emoji-id='...'> and parse_mode=HTML",
    }


@router.get("/broadcast/jobs/{job_id}", dependencies=[Depends(require_admin_auth)])
async def admin_broadcast_status(job_id: str):
    async with BROADCAST_JOBS_LOCK:
        job = BROADCAST_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="broadcast job not found")
        return {"ok": True, "job": _job_public(job)}


