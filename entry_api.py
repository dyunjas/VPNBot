import os
import asyncio
from contextlib import suppress

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from aiogram import Bot

from api.bot.endpoints import router as bot_router
from api.admin.endpoints import router as admin_router
from api.cabinet.endpoints import router as cabinet_router
from api.subscription_url.endpoints import router as subscription_router
from backend.core.config import settings
from backend.core.maintenance import MAINTENANCE_MESSAGE, is_maintenance_enabled
from backend.core.telegram import create_telegram_session
from backend.database.session import init_db, check_connection
from backend.schedulers.expire_checker import expire_checker_loop
from backend.schedulers.remnawave_sync import remnawave_sync_loop

expire_checker_task: asyncio.Task | None = None
remnawave_sync_task: asyncio.Task | None = None
runtime_bot: Bot | None = None

app = FastAPI(
    title="Lunet API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(cabinet_router)
app.include_router(subscription_router)
app.include_router(admin_router)
app.include_router(bot_router)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "API_CORS_ORIGINS",
        "http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003,http://127.0.0.1:8011,http://localhost:8001,http://localhost:8002,http://localhost:8003,http://localhost:8011",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def maintenance_guard(request: Request, call_next):
    path = request.url.path
    if (
        path.startswith("/api/admin")
        or path == "/health"
        or path == "/remnawave-webhook"
    ):
        return await call_next(request)

    if is_maintenance_enabled():
        return JSONResponse(
            status_code=503,
            content={"detail": MAINTENANCE_MESSAGE, "maintenance": True},
        )

    return await call_next(request)


@app.on_event("startup")
async def on_startup():
    global expire_checker_task, remnawave_sync_task, runtime_bot
    await init_db()
    await check_connection()

    session = create_telegram_session()
    runtime_bot = Bot(token=settings.BOT_TOKEN, session=session)
    expire_checker_task = asyncio.create_task(expire_checker_loop(runtime_bot, interval_sec=7200))
    if settings.REMNAWAVE_AUTO_SYNC_ENABLED:
        remnawave_sync_task = asyncio.create_task(remnawave_sync_loop())


@app.on_event("shutdown")
async def on_shutdown():
    global expire_checker_task, remnawave_sync_task, runtime_bot
    if expire_checker_task:
        expire_checker_task.cancel()
        with suppress(asyncio.CancelledError):
            await expire_checker_task
        expire_checker_task = None
    if remnawave_sync_task:
        remnawave_sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await remnawave_sync_task
        remnawave_sync_task = None
    if runtime_bot is not None:
        await runtime_bot.session.close()
        runtime_bot = None


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api"}


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8004"))
    uvicorn.run("entry_api:app", host="0.0.0.0", port=port)
