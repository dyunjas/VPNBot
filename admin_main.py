import os
import uvicorn
from fastapi import FastAPI
from fastapi import Request
from fastapi.staticfiles import StaticFiles

from api.admin.endpoints import router as admin_router
from backend.database.session import init_db, check_connection

app = FastAPI(title="Lunet VPN Admin")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_FRONTEND_DIR = os.path.join(BASE_DIR, "app", "admin_frontend")
print("ADMIN_FRONTEND_DIR:", ADMIN_FRONTEND_DIR)

app.mount("/admin", StaticFiles(directory=ADMIN_FRONTEND_DIR, html=True), name="admin")
app.include_router(admin_router)


@app.middleware("http")
async def disable_admin_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "lunet-admin"}


if __name__ == "__main__":
    uvicorn.run("admin_main:app", host="0.0.0.0", port=8010)
