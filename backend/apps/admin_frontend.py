from __future__ import annotations

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from backend.apps.common import ADMIN_FRONTEND_DIR, FRONTEND_DIR, create_fastapi_app, no_cache_html
from backend.core.config import settings

ADMIN_PAGES = (
    "login",
    "dashboard",
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


def _render_admin_page(name: str):
    html = (ADMIN_FRONTEND_DIR / f"{name}.html").read_text(encoding="utf-8")
    bootstrap = f"<script>window.__ADMIN_API_BASE_URL={settings.ADMIN_API_BASE_URL_JS!r};</script>"
    if '<script src="/admin/js/core/api.js' in html:
        html = html.replace('<script src="/admin/js/core/api.js', f'{bootstrap}\n  <script src="/admin/js/core/api.js', 1)
    return no_cache_html(html)


def create_app():
    app = create_fastapi_app(title="Lunet Admin Frontend")

    @app.get("/admin")
    @app.get("/admin/")
    async def admin_root():
        return FileResponse(ADMIN_FRONTEND_DIR / "index.html")

    for page in ADMIN_PAGES:
        async def page_handler(page_name: str = page):
            return _render_admin_page(page_name)

        async def legacy_handler(page_name: str = page):
            return RedirectResponse(url=f"/admin/{page_name}", status_code=307)

        app.add_api_route(f"/admin/{page}", page_handler, methods=["GET"], name=f"admin_{page}")
        app.add_api_route(f"/admin/{page}.html", legacy_handler, methods=["GET"], name=f"admin_{page}_legacy")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "admin-frontend"}

    app.mount("/admin", StaticFiles(directory=ADMIN_FRONTEND_DIR, html=False), name="admin_front_static")
    app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=False), name="miniapp_static")
    return app
