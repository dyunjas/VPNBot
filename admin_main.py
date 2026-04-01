import os
import traceback
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.admin.endpoints import router as admin_router
from backend.database.session import init_db, check_connection

app = FastAPI(
    title="Lunet VPN Admin",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_FRONTEND_DIR = os.path.join(BASE_DIR, "app", "admin_frontend")
print("ADMIN_FRONTEND_DIR:", ADMIN_FRONTEND_DIR)

@app.get("/admin")
@app.get("/admin/")
async def admin_root():
    return FileResponse(os.path.join(ADMIN_FRONTEND_DIR, "index.html"))


def _admin_page(name: str) -> FileResponse:
    return FileResponse(os.path.join(ADMIN_FRONTEND_DIR, f"{name}.html"))


@app.get("/admin/login")
async def admin_login():
    return _admin_page("login")


@app.get("/admin/dashboard")
async def admin_dashboard():
    return _admin_page("dashboard")


@app.get("/admin/users")
async def admin_users_page():
    return _admin_page("users")


@app.get("/admin/subscriptions")
async def admin_subscriptions():
    return _admin_page("subscriptions")


@app.get("/admin/plans")
async def admin_plans():
    return _admin_page("plans")


@app.get("/admin/transactions")
async def admin_transactions():
    return _admin_page("transactions")


@app.get("/admin/withdrawals")
async def admin_withdrawals():
    return _admin_page("withdrawals")


@app.get("/admin/referrals")
async def admin_referrals():
    return _admin_page("referrals")


@app.get("/admin/servers")
async def admin_servers():
    return _admin_page("servers")


@app.get("/admin/broadcast")
async def admin_broadcast():
    return _admin_page("broadcast")

@app.get("/admin/logs")
async def admin_logs():
    return _admin_page("logs")

@app.get("/admin/promocodes")
async def admin_promocodes():
    return _admin_page("promocodes")


@app.get("/admin/login.html")
async def admin_login_html():
    return RedirectResponse(url="/admin/login", status_code=307)


@app.get("/admin/dashboard.html")
async def admin_dashboard_html():
    return RedirectResponse(url="/admin/dashboard", status_code=307)


@app.get("/admin/users.html")
async def admin_users_html():
    return RedirectResponse(url="/admin/users", status_code=307)


@app.get("/admin/subscriptions.html")
async def admin_subscriptions_html():
    return RedirectResponse(url="/admin/subscriptions", status_code=307)


@app.get("/admin/plans.html")
async def admin_plans_html():
    return RedirectResponse(url="/admin/plans", status_code=307)


@app.get("/admin/transactions.html")
async def admin_transactions_html():
    return RedirectResponse(url="/admin/transactions", status_code=307)


@app.get("/admin/withdrawals.html")
async def admin_withdrawals_html():
    return RedirectResponse(url="/admin/withdrawals", status_code=307)


@app.get("/admin/referrals.html")
async def admin_referrals_html():
    return RedirectResponse(url="/admin/referrals", status_code=307)


@app.get("/admin/servers.html")
async def admin_servers_html():
    return RedirectResponse(url="/admin/servers", status_code=307)


@app.get("/admin/broadcast.html")
async def admin_broadcast_html():
    return RedirectResponse(url="/admin/broadcast", status_code=307)

@app.get("/admin/logs.html")
async def admin_logs_html():
    return RedirectResponse(url="/admin/logs", status_code=307)

@app.get("/admin/promocodes.html")
async def admin_promocodes_html():
    return RedirectResponse(url="/admin/promocodes", status_code=307)


app.mount("/admin", StaticFiles(directory=ADMIN_FRONTEND_DIR, html=False), name="admin")
app.include_router(admin_router)


@app.middleware("http")
async def disable_admin_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.exception_handler(HTTPException)
async def http_exception_json(request: Request, exc: HTTPException):
    if request.url.path.startswith("/admin-api"):
        detail = exc.detail
        if isinstance(detail, list):
            detail = "; ".join(str(item) for item in detail)
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("detail") or str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "error": {
                    "status_code": exc.status_code,
                    "message": str(detail or f"HTTP {exc.status_code}"),
                },
            },
        )
    return await fastapi_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_json(request: Request, exc: Exception):
    trace_id = uuid4().hex[:10]
    print(f"[admin-api][{trace_id}] unhandled error: {exc}\n{traceback.format_exc()}")
    if request.url.path.startswith("/admin-api"):
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "status_code": 500,
                    "message": "Internal server error",
                    "trace_id": trace_id,
                },
            },
        )
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "trace_id": trace_id})


@app.on_event("startup")
async def on_startup():
    await init_db()
    await check_connection()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "lunet-admin"}


if __name__ == "__main__":
    uvicorn.run("admin_main:app", host="0.0.0.0", port=8010)
