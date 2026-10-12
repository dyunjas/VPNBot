from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Callable

import aiohttp
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.logger_config import logger
from backend.core.config import settings
from backend.core.maintenance import MAINTENANCE_MESSAGE, get_maintenance_state
from backend.database.session import check_connection, init_db

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_STATIC_DIR = PROJECT_ROOT / "frontend" / "static"
FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "build"
LEGAL_DIR = FRONTEND_STATIC_DIR / "legal"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

TG_ID_PATH_RE = re.compile(r"/users/by-tg/(-?\d+)(?:/|$)")


def no_cache_html(content: str) -> HTMLResponse:
    return HTMLResponse(content=content, headers=NO_CACHE_HEADERS.copy())


def _request_context(request: Request) -> str:
    path = request.url.path or ""
    if path.startswith("/api/admin"):
        return "Admin API"
    if path.startswith("/api/cabinet"):
        return "Web Cabinet API"
    if path.startswith("/api/miniapp"):
        return "Telegram Mini App API"
    if path.startswith("/api/users/by-tg") or path.startswith("/api/bot"):
        return "Bot Internal API"
    if path.startswith("/api/subscription"):
        return "Subscription API"
    if path.startswith("/miniapp"):
        return "Frontend Assets"
    if path.startswith("/admin"):
        return "Admin Frontend"
    if path.startswith("/cabinet"):
        return "Web Cabinet"
    return "API"


def _request_telegram_user_id(request: Request) -> str | None:
    match = TG_ID_PATH_RE.search(request.url.path or "")
    if match:
        return match.group(1)
    for key in ("tg_id", "telegram_id", "telegram_user_id", "chat_id"):
        value = request.query_params.get(key)
        if value and value.lstrip("-").isdigit():
            return value
    return None


def create_db_lifespan() -> Callable[[FastAPI], AsyncIterator[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await init_db()
        await check_connection()
        yield

    return lifespan


def apply_common_hardening(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            limit = 10 * 1024 * 1024 if request.url.path.endswith("/broadcast/upload") else 1024 * 1024
            raw_length = request.headers.get("content-length")
            if raw_length is not None and (not raw_length.isascii() or not raw_length.isdecimal()):
                return JSONResponse({"detail": "Invalid request size"}, status_code=400)
            if raw_length is not None and int(raw_length) > limit:
                return JSONResponse({"detail": "Request is too large"}, status_code=413)
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    return JSONResponse({"detail": "Request is too large"}, status_code=413)
                chunks.append(chunk)
            # Preserve bounded bytes for the handler and post-action audit.
            request._body = b"".join(chunks)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "[app][http] unhandled exception method=%s path=%s",
                request.method,
                request.url.path,
                extra={
                    "app_context": _request_context(request),
                    "telegram_user_id": _request_telegram_user_id(request),
                },
            )
            raise
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        path = request.url.path or ""
        if path.startswith(("/api/", "/admin", "/cabinet")):
            response.headers["Cache-Control"] = "no-store"
        if path.startswith(("/admin", "/api/admin")):
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")
        if path.startswith("/api/admin") and getattr(request.state, "admin_auth", None):
            from api.admin.audit import record_admin_action
            await record_admin_action(request, request.state.admin_auth, response.status_code)
        if path.startswith("/miniapp/") and path.lower().endswith((".js", ".css", ".html")):
            for key, value in NO_CACHE_HEADERS.items():
                response.headers[key] = value
        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def create_fastapi_app(*, title: str, with_db: bool = False) -> FastAPI:
    app = FastAPI(
        title=title,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=create_db_lifespan() if with_db else None,
    )
    apply_common_hardening(app)
    return app


def register_legal_routes(app: FastAPI) -> None:
    @app.get("/terms")
    @app.get("/terms/")
    async def terms():
        return FileResponse(LEGAL_DIR / "terms.html")

    @app.get("/terms/privacy")
    @app.get("/terms/privacy/")
    async def terms_privacy():
        return FileResponse(LEGAL_DIR / "privacy.html")

    @app.get("/terms/offer")
    @app.get("/terms/offer/")
    async def terms_offer():
        return FileResponse(LEGAL_DIR / "offer.html")


async def proxy_api_request(request: Request, path: str, *, source_name: str) -> Response:
    maintenance = get_maintenance_state()
    if maintenance.get("enabled") and not (source_name == "admin-frontend" and path.startswith("admin/")):
        return JSONResponse(
            status_code=503,
            content={"detail": maintenance.get("message") or MAINTENANCE_MESSAGE, "maintenance": True},
        )

    target_url = f"{settings.API_PROXY_BASE_URL}/api/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() not in {"accept-encoding", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "forwarded"}
    }
    headers["Accept-Encoding"] = "identity"
    headers["X-Forwarded-For"] = request.client.host if request.client else "127.0.0.1"
    headers["X-Forwarded-Proto"] = request.url.scheme

    timeout = aiohttp.ClientTimeout(total=settings.FRONTEND_PROXY_TIMEOUT_SEC)
    try:
        # Preserve upstream bytes alongside Content-Encoding, including gzip responses.
        async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
            async with session.request(
                request.method,
                target_url,
                data=body or None,
                headers=headers,
                allow_redirects=False,
            ) as upstream:
                payload = await upstream.read()
                response = Response(content=payload, status_code=upstream.status)
                for key, value in upstream.headers.items():
                    if key.lower() not in HOP_BY_HOP_HEADERS:
                        response.headers.append(key, value)
                return response
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.exception(
            "[%s] API proxy failed path=%s error_type=%s",
            source_name,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={"detail": MAINTENANCE_MESSAGE, "maintenance": True},
        )


def mount_frontend_assets(app: FastAPI, *, mount_path: str = "/miniapp") -> None:
    app.mount(mount_path, StaticFiles(directory=FRONTEND_STATIC_DIR, html=False), name=f"{mount_path.strip('/')}_static")
