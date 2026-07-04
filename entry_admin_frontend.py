import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Lunet Admin Frontend",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_FRONTEND_DIR = os.path.join(BASE_DIR, "app", "admin_frontend")
FRONTEND_DIR = os.path.join(BASE_DIR, "app", "frontend")


def _render_admin_page(name: str) -> HTMLResponse:
    page_path = os.path.join(ADMIN_FRONTEND_DIR, f"{name}.html")
    with open(page_path, "r", encoding="utf-8") as f:
        html = f.read()
    api_base = os.getenv("ADMIN_API_BASE_URL", os.getenv("API_BASE_URL", "http://127.0.0.1:8004"))
    bootstrap = f"<script>window.__ADMIN_API_BASE_URL={api_base!r};</script>"
    for version in ("36", "37", "38", "39"):
        html = html.replace(f"/admin/styles.css?v={version}", "/admin/styles.css?v=40")
    for version in ("26", "27", "28", "29", "30"):
        html = html.replace(f"/admin/js/core/api.js?v={version}", "/admin/js/core/api.js?v=31")
    for version in ("26", "27", "28", "29", "30", "31"):
        html = html.replace(f"/admin/js/core/layout.js?v={version}", "/admin/js/core/layout.js?v=32")
    for version in ("29",):
        html = html.replace(f"/admin/js/pages/login.js?v={version}", "/admin/js/pages/login.js?v=30")
    for version in ("32", "33", "34", "35"):
        html = html.replace(f"/admin/js/pages/dashboard.js?v={version}", "/admin/js/pages/dashboard.js?v=36")
    if '<script src="/admin/js/core/api.js' in html:
        html = html.replace('<script src="/admin/js/core/api.js', f'{bootstrap}\n  <script src="/admin/js/core/api.js', 1)
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/admin")
@app.get("/admin/")
async def admin_root():
    return FileResponse(os.path.join(ADMIN_FRONTEND_DIR, "index.html"))


@app.get("/admin/login")
async def admin_login():
    return _render_admin_page("login")


@app.get("/admin/dashboard")
async def admin_dashboard():
    return _render_admin_page("dashboard")


@app.get("/admin/users")
async def admin_users_page():
    return _render_admin_page("users")


@app.get("/admin/subscriptions")
async def admin_subscriptions():
    return _render_admin_page("subscriptions")


@app.get("/admin/plans")
async def admin_plans():
    return _render_admin_page("plans")


@app.get("/admin/transactions")
async def admin_transactions():
    return _render_admin_page("transactions")


@app.get("/admin/withdrawals")
async def admin_withdrawals():
    return _render_admin_page("withdrawals")


@app.get("/admin/referrals")
async def admin_referrals():
    return _render_admin_page("referrals")


@app.get("/admin/broadcast")
async def admin_broadcast():
    return _render_admin_page("broadcast")


@app.get("/admin/logs")
async def admin_logs():
    return _render_admin_page("logs")


@app.get("/admin/promocodes")
async def admin_promocodes():
    return _render_admin_page("promocodes")


@app.get("/admin/partners")
async def admin_partners():
    return _render_admin_page("partners")


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


@app.get("/admin/broadcast.html")
async def admin_broadcast_html():
    return RedirectResponse(url="/admin/broadcast", status_code=307)


@app.get("/admin/logs.html")
async def admin_logs_html():
    return RedirectResponse(url="/admin/logs", status_code=307)


@app.get("/admin/promocodes.html")
async def admin_promocodes_html():
    return RedirectResponse(url="/admin/promocodes", status_code=307)


@app.get("/admin/partners.html")
async def admin_partners_html():
    return RedirectResponse(url="/admin/partners", status_code=307)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "admin-frontend"}


app.mount("/admin", StaticFiles(directory=ADMIN_FRONTEND_DIR, html=False), name="admin_front_static")
app.mount("/miniapp", StaticFiles(directory=FRONTEND_DIR, html=False), name="miniapp_static")


if __name__ == "__main__":
    port = int(os.getenv("ADMIN_FRONTEND_PORT", "8011"))
    uvicorn.run("entry_admin_frontend:app", host="0.0.0.0", port=port)
