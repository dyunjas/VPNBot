import os
import time
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from api.miniapp.endpoints import router as mini_router
from api.cabinet.endpoints import router as cabinet_router
from api.subscription_url.endpoints import router as subscription_router
from backend.database.session import async_session, init_db, check_connection

app = FastAPI(
    title="Lunet VPN MiniApp",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_DIR = os.path.join(BASE_DIR, "app", "frontend")
LEGAL_DIR = os.path.join(FRONTEND_DIR, "legal")
print("FRONTEND_DIR:", FRONTEND_DIR)

app.include_router(mini_router)
app.include_router(cabinet_router)
app.include_router(subscription_router)




@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "landing.html"))

def _render_app_shell(app_mode: str) -> HTMLResponse:
    shell_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(shell_path, "r", encoding="utf-8") as f:
        html = f.read()
    bootstrap = (
        f"<script>window.__APP_MODE={app_mode!r};</script>"
        '<script defer src="/miniapp/app.v2.js?v=18"></script>'
    )
    rendered = html.replace("__APP_BOOTSTRAP__", bootstrap)
    # Backward-compatibility: some templates may still contain old placeholder.
    rendered = rendered.replace("__APP_ENTRY__", "/miniapp/app.v2.js?v=18")
    return HTMLResponse(
        content=rendered,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/miniapp")
@app.get("/miniapp/")
async def miniapp_shell():
    return _render_app_shell("miniapp")


@app.get("/cabinet")
@app.get("/cabinet/")
async def cabinet():
    return _render_app_shell("cabinet")


@app.get("/cabinet/login")
@app.get("/cabinet/login/")
async def cabinet_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "cabinet-login.html"))


@app.get("/tg-app")
@app.get("/tg-app/")
async def tg_app():
    return RedirectResponse(url="/miniapp/", status_code=307)


@app.get("/landing")
async def landing():
    return FileResponse(os.path.join(FRONTEND_DIR, "landing.html"))


@app.get("/terms")
@app.get("/terms/")
async def terms():
    return FileResponse(os.path.join(LEGAL_DIR, "terms.html"))


@app.get("/terms/privacy")
@app.get("/terms/privacy/")
async def terms_privacy():
    return FileResponse(os.path.join(LEGAL_DIR, "privacy.html"))


@app.get("/terms/offer")
@app.get("/terms/offer/")
async def terms_offer():
    return FileResponse(os.path.join(LEGAL_DIR, "offer.html"))


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/miniapp/assets/lunet-flavicon.png?v=2", status_code=307)

@app.get("/__APP_ENTRY__")
async def legacy_app_entry():
    return RedirectResponse(url="/miniapp/app.v2.js?v=18", status_code=307)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "lunet-miniapp"}


app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=False), name="miniapp")


if __name__ == "__main__":
    uvicorn.run("app_main:app", host="0.0.0.0", port=8000)
