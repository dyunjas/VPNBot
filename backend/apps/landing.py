from __future__ import annotations

from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.apps.common import FRONTEND_BUILD_DIR, FRONTEND_STATIC_DIR, create_fastapi_app, mount_frontend_assets, register_legal_routes, proxy_api_request
from api.public.endpoints import router as public_router

LANDING_REACT_DIST = FRONTEND_BUILD_DIR / "landing"


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

    app.include_router(public_router)

    @app.get("/api/auth/session")
    async def landing_session(request: Request):
        return await proxy_api_request(request, "auth/session", source_name="landing_session")

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(FRONTEND_STATIC_DIR / "assets" / "lunet-favicon.png", media_type="image/png")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "landing"}

    mount_frontend_assets(app)
    if LANDING_REACT_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=LANDING_REACT_DIST / "assets"), name="landing_react_root_assets")
        app.mount("/landing/assets", StaticFiles(directory=LANDING_REACT_DIST / "assets"), name="landing_react_assets")
    @app.get("/{path:path}")
    async def landing_not_found(path: str):
        return FileResponse(LANDING_REACT_DIST / "404.html", status_code=404)

    return app
