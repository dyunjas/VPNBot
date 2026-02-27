import os
import time
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from api.miniapp.endpoints import router as mini_router
from api.subscription_url.endpoints import router as subscription_router
from backend.database.models import Server
from backend.database.session import async_session, init_db, check_connection

app = FastAPI(title="Lunet VPN MiniApp")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_DIR = os.path.join(BASE_DIR, "app", "frontend")
print("FRONTEND_DIR:", FRONTEND_DIR)

app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=True), name="miniapp")

app.include_router(mini_router)
app.include_router(subscription_router)

_landing_locations_cache = {
    "expires_at": 0.0,
    "items": [],
}
_landing_locations_ttl_sec = 300


async def _get_landing_locations() -> list[str]:
    now = time.monotonic()
    if _landing_locations_cache["items"] and now < float(_landing_locations_cache["expires_at"]):
        return list(_landing_locations_cache["items"])

    try:
        async with async_session() as session:
            rows = (await session.execute(select(Server.country).order_by(Server.country.asc()))).scalars().all()
    except Exception:
        rows = []

    locations = []
    seen = set()
    for value in rows:
        name = str(value or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        locations.append(name)

    if not locations:
        locations = ["Amsterdam", "Frankfurt", "London", "New York"]

    _landing_locations_cache["items"] = list(locations)
    _landing_locations_cache["expires_at"] = now + _landing_locations_ttl_sec
    return locations


@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "landing.html"))


@app.get("/landing")
async def landing():
    return FileResponse(os.path.join(FRONTEND_DIR, "landing.html"))


@app.get("/landing-data")
async def landing_data():
    locations = await _get_landing_locations()
    return {"ok": True, "locations": locations}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "lunet-miniapp"}


if __name__ == "__main__":
    uvicorn.run("app_main:app", host="0.0.0.0", port=8000)
