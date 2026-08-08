from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from backend.apps.common import create_fastapi_app, mount_frontend_assets, proxy_api_request, register_legal_routes, render_shell
from backend.core.config import settings

MINIAPP_BUILD = "20260808-gifts-devices-deeplink"


def create_app():
    app = create_fastapi_app(title="Lunet MiniApp Frontend", with_db=True)

    @app.get("/miniapp")
    @app.get("/miniapp/")
    async def miniapp_shell():
        return render_shell(
            stylesheet_urls=[
                "/miniapp/shared-tokens.css?v=1",
                "/miniapp/shared-ui.css?v=11",
                "/miniapp/miniapp.css?v=16",
            ],
            head_scripts=[
                '<script src="https://telegram.org/js/telegram-web-app.js"></script>',
            ],
            bootstrap_scripts=[
                (
                    "<script>"
                    f"window.__API_BASE_URL=window.location.origin;window.__ASSET_VERSION__='{MINIAPP_BUILD}';"
                    "window.__SURFACE='miniapp';window.__UI_MODE='miniapp';"
                    "(function(){"
                    f"const build='{MINIAPP_BUILD}';"
                    "const url=new URL(window.location.href);"
                    "const current=url.searchParams.get('__cv');"
                    "if(current!==build){"
                    "url.searchParams.set('__cv',build);"
                    "url.searchParams.set('__ts',Date.now().toString());"
                    "window.location.replace(url.toString());"
                    "return;"
                    "}"
                    "})();"
                    "</script>"
                ),
            ],
            app_entry_url=f"/miniapp/app.shared.js?v={MINIAPP_BUILD}",
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
        return RedirectResponse(url="/miniapp/assets/lunet-favicon.ico?v=7", status_code=307)

    @app.get("/__APP_ENTRY__")
    async def legacy_app_entry():
        return RedirectResponse(url=f"/miniapp/app.shared.js?v={MINIAPP_BUILD}", status_code=307)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "miniapp"}

    mount_frontend_assets(app)
    return app
