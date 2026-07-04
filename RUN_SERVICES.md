# Separate Entrypoints

Project processes:

- `entry_landing.py` -> landing frontend only
- `entry_miniapp.py` -> Telegram mini app frontend only
- `entry_cabinet.py` -> web cabinet frontend only
- `entry_admin_frontend.py` -> admin frontend only
- `entry_api.py` -> shared API service with `/api` and internal admin routes under `/api/admin`
- `main.py` -> Telegram bot

## Run examples

```powershell
$env:LANDING_PORT="8001"; python entry_landing.py
```

```powershell
$env:API_BASE_URL="http://127.0.0.1:8004"; $env:MINIAPP_PORT="8002"; python entry_miniapp.py
```

```powershell
$env:API_BASE_URL="http://127.0.0.1:8004"; $env:CABINET_PORT="8003"; python entry_cabinet.py
```

```powershell
$env:ADMIN_API_BASE_URL="http://127.0.0.1:8004"; $env:ADMIN_FRONTEND_PORT="8011"; python entry_admin_frontend.py
```

```powershell
$env:API_CORS_ORIGINS="http://127.0.0.1:8002,http://127.0.0.1:8003,http://127.0.0.1:8011,http://localhost:8002,http://localhost:8003,http://localhost:8011"; $env:API_PORT="8004"; python entry_api.py
```

```powershell
$env:API_BASE_URL="http://127.0.0.1:8004"; $env:BOT_API_TOKEN="change-me"; python entry_bot.py
```

```powershell
$env:MINIAPP_URL="https://your-miniapp-domain/miniapp/"; python main.py
```

## Notes

- For production, route the domains/paths through a reverse proxy.
- Shared assets, backend, and database stay common across the apps.
