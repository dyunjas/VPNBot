from __future__ import annotations
import json
import secrets

from fastapi import Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from backend.apps.common import FRONTEND_BUILD_DIR, FRONTEND_STATIC_DIR, create_fastapi_app, no_cache_html, proxy_api_request

ADMIN_PAGES = (
    "login",
    "dashboard",
    "maintenance",
    "diagnostics",
    "admins",
    "legal",
    "users",
    "subscriptions",
    "plans",
    "transactions",
    "withdrawals",
    "referrals",
    "broadcast",
    "logs",
    "promocodes",
    "partners",
)

ADMIN_REACT_DIST = FRONTEND_BUILD_DIR / "admin"


def _react_app_available() -> bool:
    return (ADMIN_REACT_DIST / "index.html").is_file()


def _react_index_response():
    html = (ADMIN_REACT_DIST / "index.html").read_text(encoding="utf-8")
    nonce = secrets.token_urlsafe(24)
    # The browser always uses the admin host: __Host cookies cannot span hosts.
    value = json.dumps("")
    bootstrap = f'<script nonce="{nonce}">window.__ADMIN_API_BASE_URL={value};</script>'
    response = no_cache_html(html.replace("</head>", f"{bootstrap}</head>", 1))
    connection = ""
    response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'{connection}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
    return response


def _render_admin_page(name: str):
    return _react_index_response()


def create_app():
    app = create_fastapi_app(title="Lunet Admin Frontend")

    async def protected_page(request: Request):
        from backend.services.admin_security import validate_session
        try:
            await validate_session(request)
        except HTTPException as error:
            if error.status_code in {401, 403}:
                return RedirectResponse(url="/admin/login", status_code=303)
            raise
        return _react_index_response()

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/admin/", status_code=307)

    @app.get("/admin")
    @app.get("/admin/")
    async def admin_root(request: Request):
        return await protected_page(request)

    @app.get("/admin/manifest.webmanifest", include_in_schema=False)
    async def admin_manifest():
        return FileResponse(ADMIN_REACT_DIST / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/admin/sw.js", include_in_schema=False)
    async def admin_service_worker():
        return FileResponse(ADMIN_REACT_DIST / "sw.js", media_type="application/javascript")

    for page in ADMIN_PAGES:
        async def page_handler(request: Request):
            return _render_admin_page("login") if request.url.path == "/admin/login" else await protected_page(request)

        app.add_api_route(f"/admin/{page}", page_handler, methods=["GET"], name=f"admin_{page}")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "admin-frontend"}

    @app.api_route("/api/admin/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def admin_api_proxy(request: Request, path: str):
        return await proxy_api_request(request, "admin/" + path, source_name="admin-frontend")

    if _react_app_available():
        app.mount("/admin/assets", StaticFiles(directory=ADMIN_REACT_DIST / "assets", html=False), name="admin_react_assets")
    @app.get("/admin/{path:path}")
    async def admin_not_found(path: str):
        response = _react_index_response()
        return HTMLResponse(content=response.body, status_code=404, headers=dict(response.headers))

    app.mount("/miniapp", StaticFiles(directory=FRONTEND_STATIC_DIR, html=False), name="miniapp_static")
    return app
