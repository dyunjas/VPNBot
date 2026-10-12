from __future__ import annotations

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.apps.common import FRONTEND_BUILD_DIR, FRONTEND_STATIC_DIR, create_fastapi_app, mount_frontend_assets, no_cache_html, proxy_api_request, register_legal_routes

CABINET_REACT_DIST = FRONTEND_BUILD_DIR / "cabinet"


def create_app():
    app = create_fastapi_app(title="Lunet Cabinet Frontend", with_db=True)

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/cabinet/", status_code=307)

    @app.get("/cabinet")
    @app.get("/cabinet/")
    async def cabinet():
        return no_cache_html((CABINET_REACT_DIST / "index.html").read_text(encoding="utf-8"))

    @app.get("/cabinet/login")
    @app.get("/cabinet/login/")
    async def cabinet_login():
        return no_cache_html((CABINET_REACT_DIST / "index.html").read_text(encoding="utf-8"))

    @app.get("/cabinet/manifest.webmanifest")
    async def cabinet_manifest():
        return FileResponse(CABINET_REACT_DIST / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/cabinet/sw.js")
    async def cabinet_service_worker():
        return FileResponse(CABINET_REACT_DIST / "sw.js", media_type="application/javascript")

    @app.get("/cabinet/auth/deeplink/{token}")
    async def cabinet_deeplink(token: str):
        import re
        from fastapi import HTTPException
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
            raise HTTPException(400, "Invalid login link")
        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Вход в кабинет | Lunet</title>
  <style>body{{margin:0;background:#fafafa;color:#18181b;font-family:Inter,Arial,sans-serif}}.auth-page{{min-height:100vh;display:grid;place-items:center;padding:24px;box-sizing:border-box}}.auth-card{{width:min(420px,100%);padding:28px;border:1px solid #e4e4e7;border-radius:12px;background:#fff;box-shadow:0 12px 36px #0000000d}}.auth-card__logo{{width:42px;height:42px;object-fit:contain}}.auth-card__head h2{{margin:22px 0 8px;font-size:24px}}.status{{color:#71717a;font-size:14px;line-height:1.5}}.status.error{{color:#dc2626}}</style>
</head>
<body>
  <main class="auth-page">
    <section class="auth-layout">
      <section class="auth-card">
        <div class="auth-card__brand"><img class="auth-card__logo" src="/miniapp/assets/lunet-logo-sign.png" alt="Lunet" /></div>
        <div class="auth-card__head"><h2>Вход в кабинет</h2></div>
        <p id="status" class="status">Проверяем ссылку...</p>
      </section>
    </section>
  </main>
  <script>
    (async () => {{
      const status = document.getElementById("status");
      try {{
        const res = await fetch("/api/auth/deeplink/consume", {{
          method: "POST",
          credentials: "include",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ initData: {token!r} }})
        }});
        const data = await res.json().catch(() => ({{}}));
        if (!res.ok || !data.access_token) throw new Error(data.detail || "Ссылка недействительна");
        localStorage.setItem("cabinet_access_token", data.access_token);
        window.location.replace("/cabinet");
      }} catch (error) {{
        status.textContent = error.message || "Не удалось войти по ссылке";
        status.classList.add("error");
      }}
    }})();
  </script>
</body>
</html>"""
        return no_cache_html(html)

    register_legal_routes(app)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy_api(request: Request, path: str):
        return await proxy_api_request(request, path, source_name="cabinet_proxy")

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(FRONTEND_STATIC_DIR / "assets" / "lunet-favicon.png", media_type="image/png")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cabinet"}

    if CABINET_REACT_DIST.is_dir():
        app.mount("/cabinet/assets", StaticFiles(directory=CABINET_REACT_DIST / "assets"), name="cabinet_react_assets")
    @app.get("/cabinet/{path:path}")
    async def cabinet_not_found(path: str):
        html = (CABINET_REACT_DIST / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html, status_code=404, headers={"Cache-Control": "no-store"})

    mount_frontend_assets(app)
    return app
