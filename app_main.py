import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.miniapp.endpoints import router as mini_router
from api.subscription_url.endpoints import router as subscription_router
from backend.database.session import init_db, check_connection

app = FastAPI(title="Lunet VPN MiniApp")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_DIR = os.path.join(BASE_DIR, "app", "frontend")
print("FRONTEND_DIR:", FRONTEND_DIR)

app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=True), name="miniapp")

app.include_router(mini_router)
app.include_router(subscription_router)


@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


@app.get("/")
async def root():
    return {"status": "ok", "service": "lunet-miniapp"}


if __name__ == "__main__":
    uvicorn.run("app_main:app", host="0.0.0.0", port=8000)
