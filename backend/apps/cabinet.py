from __future__ import annotations

from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse

from backend.apps.common import FRONTEND_DIR, create_fastapi_app, mount_frontend_assets, no_cache_html, proxy_api_request, register_legal_routes, render_shell
from backend.core.config import settings

CABINET_BUILD = "20260808-cabinet-responsive-fix"


def create_app():
    app = create_fastapi_app(title="Lunet Cabinet Frontend", with_db=True)

    @app.get("/cabinet")
    @app.get("/cabinet/")
    async def cabinet():
        return render_shell(
            stylesheet_urls=[
                "/miniapp/shared-tokens.css?v=1",
                "/miniapp/shared-ui.css?v=11",
                "/miniapp/miniapp.css?v=16",
            ],
            bootstrap_scripts=[
                (
                    "<script>"
                    f"window.__API_BASE_URL=window.location.origin;window.__ASSET_VERSION__='{CABINET_BUILD}';"
                    "window.__SURFACE='cabinet';window.__UI_MODE='cabinet';"
                    "</script>"
                ),
            ],
            app_entry_url=f"/miniapp/app.shared.js?v={CABINET_BUILD}",
        )

    @app.get("/cabinet/login")
    @app.get("/cabinet/login/")
    async def cabinet_login():
        html = (FRONTEND_DIR / "cabinet-login.html").read_text(encoding="utf-8")
        rendered = html.replace(
            "__API_BOOTSTRAP__",
            "<script>window.__API_BASE_URL=window.location.origin;</script>",
        )
        return no_cache_html(rendered)

    @app.get("/cabinet/auth/deeplink/{token}")
    async def cabinet_deeplink(token: str):
        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Вход в кабинет | Lunet</title>
  <link rel="stylesheet" href="/miniapp/cabinet-auth.css?v=22" />
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
        return FileResponse(FRONTEND_DIR / "assets" / "lunet-favicon.ico")

    @app.get("/__APP_ENTRY__")
    async def legacy_app_entry():
        return RedirectResponse(url=f"/miniapp/app.shared.js?v={CABINET_BUILD}", status_code=307)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cabinet"}

    mount_frontend_assets(app)
    return app
