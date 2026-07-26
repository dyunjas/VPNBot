from __future__ import annotations

from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse

from backend.apps.common import FRONTEND_DIR, create_fastapi_app, mount_frontend_assets, no_cache_html, proxy_api_request, register_legal_routes, render_shell
from backend.core.config import settings


def create_app():
    app = create_fastapi_app(title="Lunet Cabinet Frontend", with_db=True)

    @app.get("/cabinet")
    @app.get("/cabinet/")
    async def cabinet():
        return render_shell(
            stylesheet_urls=[
                "/miniapp/shared-tokens.css?v=1",
                "/miniapp/shared-ui.css?v=8",
                "/miniapp/cabinet.css?v=27",
            ],
            bootstrap_scripts=[
                "<script>window.__API_BASE_URL=window.location.origin;</script>",
                '<script defer src="/miniapp/cabinet-app.js?v=3"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-01.js?v=7"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-02.js?v=15"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-03.js?v=10"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-04.js?v=9"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-05.js?v=6"></script>',
            ],
            app_entry_url="/miniapp/app.shared.js?v=3",
        )

    @app.get("/cabinet/login")
    @app.get("/cabinet/login/")
    async def cabinet_login():
        html = (FRONTEND_DIR / "cabinet-login.html").read_text(encoding="utf-8")
        rendered = html.replace(
            "__API_BOOTSTRAP__",
            "<script>window.__API_BASE_URL=window.location.origin;</script>",
        )
        return no_cache_html(rendered)

    register_legal_routes(app)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy_api(request: Request, path: str):
        return await proxy_api_request(request, path, source_name="cabinet_proxy")

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(FRONTEND_DIR / "assets" / "lunet-favicon.ico")

    @app.get("/__APP_ENTRY__")
    async def legacy_app_entry():
        return RedirectResponse(url="/miniapp/app.shared.js?v=3", status_code=307)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cabinet"}

    mount_frontend_assets(app)
    return app
