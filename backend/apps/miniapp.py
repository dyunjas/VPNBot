from __future__ import annotations

from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.apps.common import FRONTEND_BUILD_DIR, FRONTEND_STATIC_DIR, create_fastapi_app, mount_frontend_assets, no_cache_html, proxy_api_request, register_legal_routes

MINIAPP_REACT_DIST = FRONTEND_BUILD_DIR / "miniapp"


def create_app():
    app = create_fastapi_app(title="Lunet MiniApp Frontend", with_db=True)

    @app.get("/miniapp")
    @app.get("/miniapp/")
    async def miniapp_shell():
        return no_cache_html((MINIAPP_REACT_DIST / "index.html").read_text(encoding="utf-8"))

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
        return FileResponse(FRONTEND_STATIC_DIR / "assets" / "lunet-favicon.png", media_type="image/png")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "miniapp"}

    if MINIAPP_REACT_DIST.is_dir():
        app.mount(
            "/miniapp/react-assets",
            StaticFiles(directory=MINIAPP_REACT_DIST / "react-assets"),
            name="miniapp_react_assets",
        )
    mount_frontend_assets(app)
    return app
