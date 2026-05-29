# Separate Entrypoints

Проект разнесен на отдельные процессы:

- `entry_landing.py` -> лендинг (по умолчанию порт `8001`)
- `entry_miniapp.py` -> Telegram mini app frontend-only (порт `8002`)
- `entry_cabinet.py` -> web кабинет frontend-only (порт `8003`)
- `entry_admin_frontend.py` -> админка frontend-only (порт `8011`)
- `entry_api.py` -> общий API-only сервис (включая `admin-api`) (порт `8004`)
- `main.py` -> Telegram bot

## Пример запуска (PowerShell)

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
$env:MINIAPP_URL="https://your-miniapp-domain/miniapp/"; python main.py
```

## Важно

- Для production лучше вынести маршрутизацию на reverse proxy (nginx/traefik/caddy) и проксировать домены/пути на эти порты.
- Стили/ассеты общие (`app/frontend`), backend и БД общие.
