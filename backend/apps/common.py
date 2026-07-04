from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Callable

import aiohttp
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.core.maintenance import MAINTENANCE_MESSAGE, get_maintenance_state
from backend.database.session import check_connection, init_db

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "app" / "frontend"
ADMIN_FRONTEND_DIR = PROJECT_ROOT / "app" / "admin_frontend"
LEGAL_DIR = FRONTEND_DIR / "legal"
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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def no_cache_html(content: str) -> HTMLResponse:
    return HTMLResponse(content=content, headers=NO_CACHE_HEADERS.copy())


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
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
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


def render_shell(
    *,
    stylesheet_urls: list[str],
    bootstrap_scripts: list[str],
    app_entry_url: str,
    head_scripts: list[str] | None = None,
) -> HTMLResponse:
    html = _read_text(FRONTEND_DIR / "shell.html")
    app_shell = _read_text(FRONTEND_DIR / "shell" / "app-shell.html")
    sidebar = _read_text(FRONTEND_DIR / "shell" / "sidebar.html")
    main = _read_text(FRONTEND_DIR / "shell" / "main.html")
    footer_nav = _read_text(FRONTEND_DIR / "shell" / "footer-nav.html")

    styles = "".join(f'<link rel="stylesheet" href="{url}" />' for url in stylesheet_urls)
    rendered = (
        html.replace(
            "__APP_SHELL__",
            app_shell
            .replace("__SHELL_SIDEBAR__", sidebar)
            .replace("__SHELL_MAIN__", main)
            .replace("__SHELL_FOOTER_NAV__", footer_nav),
        )
        .replace("__SURFACE_STYLES__", styles)
        .replace("__HEAD_SCRIPTS__", "".join(head_scripts or []))
        .replace("__APP_BOOTSTRAP__", "".join(bootstrap_scripts))
        .replace("__APP_ENTRY__", app_entry_url)
    )
    return no_cache_html(rendered)


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
    if maintenance.get("enabled"):
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
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    timeout = aiohttp.ClientTimeout(total=settings.FRONTEND_PROXY_TIMEOUT_SEC)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return JSONResponse(
            status_code=503,
            content={"detail": MAINTENANCE_MESSAGE, "maintenance": True},
        )


def mount_frontend_assets(app: FastAPI, *, mount_path: str = "/miniapp") -> None:
    app.mount(mount_path, StaticFiles(directory=FRONTEND_DIR, html=False), name=f"{mount_path.strip('/')}_static")
