from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from aiogram import Bot
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.admin.endpoints import router as admin_router
from api.bot.endpoints import router as bot_router
from api.cabinet.endpoints import router as cabinet_router
from api.subscription_url.endpoints import router as subscription_router
from backend.apps.common import apply_common_hardening
from backend.core.config import settings
from backend.core.maintenance import MAINTENANCE_MESSAGE, is_maintenance_enabled
from backend.core.telegram import create_telegram_session
from backend.database.session import check_connection, init_db
from backend.schedulers.expire_checker import expire_checker_loop
from backend.schedulers.remnawave_sync import remnawave_sync_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await check_connection()

    session = create_telegram_session()
    runtime_bot = Bot(token=settings.BOT_TOKEN, session=session)
    expire_checker_task = asyncio.create_task(expire_checker_loop(runtime_bot, interval_sec=7200))
    remnawave_sync_task = (
        asyncio.create_task(remnawave_sync_loop())
        if settings.REMNAWAVE_AUTO_SYNC_ENABLED
        else None
    )

    try:
        yield
    finally:
        expire_checker_task.cancel()
        with suppress(asyncio.CancelledError):
            await expire_checker_task
        if remnawave_sync_task:
            remnawave_sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await remnawave_sync_task
        await runtime_bot.session.close()


def create_app():
    app = FastAPI(
        title="Lunet API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    apply_common_hardening(app)

    app.include_router(cabinet_router)
    app.include_router(subscription_router)
    app.include_router(admin_router)
    app.include_router(bot_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.API_CORS_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "X-Bot-Token", "X-Requested-With"],
    )

    @app.middleware("http")
    async def maintenance_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/admin") or path == "/health" or path == "/remnawave-webhook":
            return await call_next(request)

        if is_maintenance_enabled():
            return JSONResponse(
                status_code=503,
                content={"detail": MAINTENANCE_MESSAGE, "maintenance": True},
            )

        return await call_next(request)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "api"}

    return app

