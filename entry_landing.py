import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.database.session import init_db, check_connection

app = FastAPI(
    title="Lunet Landing",
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


@app.get("/")
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "landing"}


# Landing uses shared frontend assets/styles from the same frontend dir.
app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=False), name="miniapp_assets")


if __name__ == "__main__":
    port = int(os.getenv("LANDING_PORT", "8001"))
    uvicorn.run("entry_landing:app", host="0.0.0.0", port=port)
