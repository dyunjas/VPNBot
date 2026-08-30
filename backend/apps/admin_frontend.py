from __future__ import annotations

from fastapi.staticfiles import StaticFiles
from backend.apps.common import ADMIN_FRONTEND_DIR, FRONTEND_DIR, create_fastapi_app, no_cache_html
from backend.core.config import settings

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

ADMIN_REACT_DIST = ADMIN_FRONTEND_DIR / "dist"


def _react_app_available() -> bool:
    return (ADMIN_REACT_DIST / "index.html").is_file()


def _react_index_response():
    html = (ADMIN_REACT_DIST / "index.html").read_text(encoding="utf-8")
    bootstrap = f"<script>window.__ADMIN_API_BASE_URL={settings.ADMIN_API_BASE_URL_JS!r};</script>"
    return no_cache_html(html.replace("</head>", f"{bootstrap}</head>", 1))


def _render_admin_page(name: str):
    return _react_index_response()


def create_app():
    app = create_fastapi_app(title="Lunet Admin Frontend")

    @app.get("/admin")
    @app.get("/admin/")
    async def admin_root():
        return _react_index_response()

    for page in ADMIN_PAGES:
        async def page_handler(page_name: str = page):
            return _render_admin_page(page_name)

        app.add_api_route(f"/admin/{page}", page_handler, methods=["GET"], name=f"admin_{page}")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "admin-frontend"}

    if _react_app_available():
        app.mount("/admin/assets", StaticFiles(directory=ADMIN_REACT_DIST / "assets", html=False), name="admin_react_assets")
    app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=False), name="miniapp_static")
    return app
