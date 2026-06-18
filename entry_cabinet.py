import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.database.session import init_db, check_connection

app = FastAPI(
    title="Lunet Cabinet Frontend",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "app", "frontend")
LEGAL_DIR = os.path.join(FRONTEND_DIR, "legal")

@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


def _render_shell(app_mode: str) -> HTMLResponse:
    shell_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(shell_path, "r", encoding="utf-8") as f:
        html = f.read()
    api_base = os.getenv("API_BASE_URL", "http://127.0.0.1:8004")
    bootstrap = (
        f"<script>window.__APP_MODE={app_mode!r};</script>"
        f"<script>window.__API_BASE_URL={api_base!r};</script>"
        '<script defer src="/miniapp/app.v2.js?v=18"></script>'
    )
    rendered = html.replace("__APP_BOOTSTRAP__", bootstrap).replace("__APP_ENTRY__", "/miniapp/app.v2.js?v=18")
    return HTMLResponse(
        content=rendered,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/cabinet")
@app.get("/cabinet/")
async def cabinet():
    return _render_shell("cabinet")


@app.get("/cabinet/login")
@app.get("/cabinet/login/")
async def cabinet_login():
    login_path = os.path.join(FRONTEND_DIR, "cabinet-login.html")
    with open(login_path, "r", encoding="utf-8") as f:
        html = f.read()
    api_base = os.getenv("API_BASE_URL", "http://127.0.0.1:8004")
    bootstrap = f"<script>window.__API_BASE_URL={api_base!r};</script>"
    rendered = html.replace("__API_BOOTSTRAP__", bootstrap)
    return HTMLResponse(
        content=rendered,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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
    return {"status": "ok", "service": "cabinet"}


app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=False), name="cabinet_static")


if __name__ == "__main__":
    port = int(os.getenv("CABINET_PORT", "8003"))
    uvicorn.run("entry_cabinet:app", host="0.0.0.0", port=port)
