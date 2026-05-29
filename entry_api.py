import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin.endpoints import router as admin_router
from api.miniapp.endpoints import router as mini_router
from api.cabinet.endpoints import router as cabinet_router
from api.subscription_url.endpoints import router as subscription_router
from backend.database.session import init_db, check_connection

app = FastAPI(
    title="Lunet API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(mini_router)
app.include_router(cabinet_router)
app.include_router(subscription_router)
app.include_router(admin_router)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "API_CORS_ORIGINS",
        "http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003,http://127.0.0.1:8011,http://localhost:8001,http://localhost:8002,http://localhost:8003,http://localhost:8011",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api"}


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8004"))
    uvicorn.run("entry_api:app", host="0.0.0.0", port=port)
