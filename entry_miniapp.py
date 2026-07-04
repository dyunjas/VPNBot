import os
import asyncio
import uvicorn
import aiohttp
from fastapi import FastAPI
from fastapi import Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.maintenance import MAINTENANCE_MESSAGE, enable_auto_maintenance, get_maintenance_state
from backend.database.session import init_db, check_connection

app = FastAPI(
    title="Lunet MiniApp Frontend",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "app", "frontend")
LEGAL_DIR = os.path.join(FRONTEND_DIR, "legal")
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

@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


def _render_shell() -> HTMLResponse:
    shell_path = os.path.join(FRONTEND_DIR, "shell.html")
    app_shell_path = os.path.join(FRONTEND_DIR, "shell", "app-shell.html")
    sidebar_path = os.path.join(FRONTEND_DIR, "shell", "sidebar.html")
    main_path = os.path.join(FRONTEND_DIR, "shell", "main.html")
    footer_nav_path = os.path.join(FRONTEND_DIR, "shell", "footer-nav.html")
    with open(shell_path, "r", encoding="utf-8") as f:
        html = f.read()
    with open(app_shell_path, "r", encoding="utf-8") as f:
        app_shell = f.read()
    with open(sidebar_path, "r", encoding="utf-8") as f:
        sidebar = f.read()
    with open(main_path, "r", encoding="utf-8") as f:
        main = f.read()
    with open(footer_nav_path, "r", encoding="utf-8") as f:
        footer_nav = f.read()
    api_base = (os.getenv("API_BASE_URL") or "").strip()
    styles = (
        '<link rel="stylesheet" href="/miniapp/shared-tokens.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/shared-ui.css?v=4" />'
        '<link rel="stylesheet" href="/miniapp/miniapp.css?v=5" />'
    )
    head_scripts = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'
    bootstrap = (
        f"<script>window.__API_BASE_URL={api_base!r};</script>"
        '<script defer src="/miniapp/miniapp-app.js?v=3"></script>'
        '<script defer src="/miniapp/shared-js/app.shared-01.js?v=4"></script>'
        '<script defer src="/miniapp/shared-js/app.shared-02.js?v=4"></script>'
        '<script defer src="/miniapp/shared-js/app.shared-03.js?v=4"></script>'
        '<script defer src="/miniapp/shared-js/app.shared-04.js?v=4"></script>'
        '<script defer src="/miniapp/shared-js/app.shared-05.js?v=4"></script>'
    )
    rendered = (
        html
        .replace(
            "__APP_SHELL__",
            app_shell
            .replace("__SHELL_SIDEBAR__", sidebar)
            .replace("__SHELL_MAIN__", main)
            .replace("__SHELL_FOOTER_NAV__", footer_nav),
        )
        .replace("__SURFACE_STYLES__", styles)
        .replace("__HEAD_SCRIPTS__", head_scripts)
        .replace("__APP_BOOTSTRAP__", bootstrap)
        .replace("__APP_ENTRY__", "/miniapp/app.shared.js?v=3")
    )
    return HTMLResponse(
        content=rendered,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/miniapp")
@app.get("/miniapp/")
async def miniapp_shell():
    return _render_shell()


@app.get("/tg-app")
@app.get("/tg-app/")
async def tg_app():
    return RedirectResponse(url="/miniapp/", status_code=307)


@app.get("/terms")
@app.get("/terms/")
async def terms():
    return FileResponse(os.path.join(LEGAL_DIR, "terms.html"))


@app.get("/terms/privacy")
@app.get("/terms/privacy/")
async def terms_privacy():
    return FileResponse(os.path.join(LEGAL_DIR, "privacy.html"))


@app.get("/terms/offer")
@app.get("/terms/offer/")
async def terms_offer():
    return FileResponse(os.path.join(LEGAL_DIR, "offer.html"))


async def _proxy_api(request: Request, path: str) -> Response:
    maintenance = get_maintenance_state()
    if maintenance.get("enabled"):
        return JSONResponse(
            status_code=503,
            content={"detail": maintenance.get("message") or MAINTENANCE_MESSAGE, "maintenance": True},
        )
    api_base = (os.getenv("API_BASE_URL") or "http://127.0.0.1:8004").rstrip("/")
    target_url = f"{api_base}/api/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    timeout = aiohttp.ClientTimeout(total=60)
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
        enable_auto_maintenance(source="miniapp_proxy", message=MAINTENANCE_MESSAGE)
        return JSONResponse(
            status_code=503,
            content={"detail": MAINTENANCE_MESSAGE, "maintenance": True},
        )


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_api(request: Request, path: str):
    return await _proxy_api(request, path)


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/miniapp/assets/lunet-flavicon.png?v=2", status_code=307)


@app.get("/__APP_ENTRY__")
async def legacy_app_entry():
    return RedirectResponse(url="/miniapp/app.shared.js?v=3", status_code=307)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "miniapp"}


app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=False), name="miniapp_static")


if __name__ == "__main__":
    port = int(os.getenv("MINIAPP_PORT", "8002"))
    uvicorn.run("entry_miniapp:app", host="0.0.0.0", port=port)
