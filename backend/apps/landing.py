from __future__ import annotations

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.apps.common import FRONTEND_DIR, create_fastapi_app, mount_frontend_assets, register_legal_routes

LANDING_REACT_DIST = FRONTEND_DIR / "landing_dist"


def create_app():
    app = create_fastapi_app(title="Lunet Landing", with_db=True)

    @app.get("/")
    @app.get("/landing")
    async def landing():
        return FileResponse(LANDING_REACT_DIST / "index.html")

    @app.get("/cabinet")
    @app.get("/cabinet/")
    async def cabinet_redirect():
        return RedirectResponse(url="https://app.lunet.pro/cabinet", status_code=307)

    @app.get("/cabinet/login")
    @app.get("/cabinet/login/")
    async def cabinet_login_redirect():
        return RedirectResponse(url="https://app.lunet.pro/cabinet/login", status_code=307)

    register_legal_routes(app)

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(FRONTEND_DIR / "assets" / "lunet-favicon.png", media_type="image/png")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "landing"}

    mount_frontend_assets(app)
    if LANDING_REACT_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=LANDING_REACT_DIST / "assets"), name="landing_react_root_assets")
        app.mount("/landing/assets", StaticFiles(directory=LANDING_REACT_DIST / "assets"), name="landing_react_assets")
    return app
