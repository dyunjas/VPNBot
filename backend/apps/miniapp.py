from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from backend.apps.common import create_fastapi_app, mount_frontend_assets, proxy_api_request, register_legal_routes, render_shell
from backend.core.config import settings


def create_app():
    app = create_fastapi_app(title="Lunet MiniApp Frontend", with_db=True)

    @app.get("/miniapp")
    @app.get("/miniapp/")
    async def miniapp_shell():
        return render_shell(
            stylesheet_urls=[
                "/miniapp/shared-tokens.css?v=1",
                "/miniapp/shared-ui.css?v=8",
                "/miniapp/miniapp.css?v=9",
            ],
            head_scripts=['<script src="https://telegram.org/js/telegram-web-app.js"></script>'],
            bootstrap_scripts=[
                "<script>window.__API_BASE_URL=window.location.origin;</script>",
                '<script defer src="/miniapp/miniapp-app.js?v=3"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-01.js?v=4"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-02.js?v=13"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-03.js?v=6"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-04.js?v=4"></script>',
                '<script defer src="/miniapp/shared-js/app.shared-05.js?v=4"></script>',
            ],
            app_entry_url="/miniapp/app.shared.js?v=3",
        )

    @app.get("/tg-app")
    @app.get("/tg-app/")
    async def tg_app():
        return RedirectResponse(url="/miniapp/", status_code=307)

    register_legal_routes(app)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy_api(request: Request, path: str):
        return await proxy_api_request(request, path, source_name="miniapp_proxy")

    @app.get("/favicon.ico")
    async def favicon():
        return RedirectResponse(url="/miniapp/assets/lunet-flavicon.png?v=2", status_code=307)

    @app.get("/__APP_ENTRY__")
    async def legacy_app_entry():
        return RedirectResponse(url="/miniapp/app.shared.js?v=3", status_code=307)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "miniapp"}

    mount_frontend_assets(app)
    return app
