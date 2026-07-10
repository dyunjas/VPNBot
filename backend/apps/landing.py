from __future__ import annotations

from fastapi.responses import FileResponse, RedirectResponse

from backend.apps.common import FRONTEND_DIR, create_fastapi_app, mount_frontend_assets, register_legal_routes


def create_app():
    app = create_fastapi_app(title="Lunet Landing", with_db=True)

    @app.get("/")
    @app.get("/landing")
    async def landing():
        return FileResponse(FRONTEND_DIR / "landing.html")

    @app.get("/cabinet")
    @app.get("/cabinet/")
    async def cabinet_redirect():
        return RedirectResponse(url="https://app.lunetpn.ru/cabinet", status_code=307)

    @app.get("/cabinet/login")
    @app.get("/cabinet/login/")
    async def cabinet_login_redirect():
        return RedirectResponse(url="https://app.lunetpn.ru/cabinet/login", status_code=307)

    register_legal_routes(app)

    @app.get("/favicon.ico")
    async def favicon():
        return RedirectResponse(url="/miniapp/assets/lunet-favicon.ico?v=7", status_code=307)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "landing"}

    mount_frontend_assets(app)
    return app
