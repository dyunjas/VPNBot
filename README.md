# VPNBot

Сервис разделен на отдельные процессы:

- `landing` - публичный лендинг
- `miniapp` - Telegram Mini App frontend
- `cabinet` - web cabinet frontend
- `admin` - админский frontend
- `api` - общий FastAPI backend
- `bot` - Telegram bot

## Быстрый старт

```powershell
python manage.py bootstrap
```

После установки зависимости и виртуальное окружение будут подготовлены автоматически.

## Запуск сервисов

```powershell
python manage.py run landing
python manage.py run miniapp
python manage.py run cabinet
python manage.py run admin
python manage.py run api
python manage.py run bot
```

## Архитектура

- Старые `entry_*.py` оставлены как тонкие точки входа.
- Реальная сборка приложений вынесена в `backend/apps/`.
- Общий runtime и uvicorn-настройки вынесены в `backend/core/runtime.py`.
- Общие frontend helper'ы и proxy-логика вынесены в `backend/apps/common.py`.

## Базовая безопасность

- Mini App API проверяет подпись `initData` от Telegram и ограничивает срок ее жизни.
- Cabinet использует короткоживущий access token и refresh token в `httpOnly` cookie.
- Admin использует JWT со scope `admin:web`, cookie `httpOnly` и rate limit на логин.
- Bot API теперь принимает только отдельный `BOT_API_TOKEN`; fallback на `SECRET_KEY` убран.
- Для всех HTTP-приложений включены `TrustedHostMiddleware` и базовые security headers.

## Что нужно настроить в production

- `TRUSTED_HOSTS` - реальные домены приложения.
- `API_CORS_ORIGINS` - только допустимые frontend origin'ы.
- `UVICORN_FORWARDED_ALLOW_IPS` - IP вашего reverse proxy.
- HTTPS на уровне reverse proxy, чтобы `secure` cookie и HSTS работали корректно.
