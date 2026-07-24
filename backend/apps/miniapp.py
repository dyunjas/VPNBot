from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from backend.apps.common import create_fastapi_app, mount_frontend_assets, proxy_api_request, register_legal_routes, render_shell
from backend.core.config import settings

MINIAPP_BUILD = "20260725-0004"


def create_app():
    app = create_fastapi_app(title="Lunet MiniApp Frontend", with_db=True)

    @app.get("/miniapp")
    @app.get("/miniapp/")
    async def miniapp_shell():
        return render_shell(
            stylesheet_urls=[
                "/miniapp/shared-tokens.css?v=1",
                "/miniapp/shared-ui.css?v=9",
                "/miniapp/miniapp.css?v=10",
            ],
            head_scripts=[
                '<script src="https://telegram.org/js/telegram-web-app.js"></script>',
                (
                    "<style>"
                    "body.is-miniapp{"
                    "background:"
                    "radial-gradient(circle at top left, rgba(255,255,255,.28), transparent 28%),"
                    "linear-gradient(180deg,#5b7cfa 0%,#4f74f7 100%) !important;"
                    "background-color:#5b7cfa !important;"
                    "}"
                    ".is-miniapp .pay-method--active{"
                    "border-color:#4c6fff !important;"
                    "background:linear-gradient(180deg,#f3f6ff 0%,#ebf1ff 100%) !important;"
                    "box-shadow:0 0 0 2px rgba(76,111,255,.26),0 12px 28px rgba(76,111,255,.16) !important;"
                    "}"
                    ".is-miniapp .bottom-nav,.is-miniapp .tab{border-color:#dbe6f6 !important;}"
                    "</style>"
                ),
            ],
            bootstrap_scripts=[
                (
                    "<script>"
                    f"window.__API_BASE_URL=window.location.origin;window.__ASSET_VERSION__='{MINIAPP_BUILD}';"
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
                f'<script defer src="/miniapp/miniapp-app.js?v={MINIAPP_BUILD}"></script>',
                f'<script defer src="/miniapp/shared-js/app.shared-01.js?v={MINIAPP_BUILD}"></script>',
                f'<script defer src="/miniapp/shared-js/app.shared-02.js?v={MINIAPP_BUILD}"></script>',
                f'<script defer src="/miniapp/shared-js/app.shared-03.js?v={MINIAPP_BUILD}"></script>',
                f'<script defer src="/miniapp/shared-js/app.shared-04.js?v={MINIAPP_BUILD}"></script>',
                f'<script defer src="/miniapp/shared-js/app.shared-05.js?v={MINIAPP_BUILD}"></script>',
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
