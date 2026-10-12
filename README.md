# Lunet VPS

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

- `frontend/` — четыре приложения, общие компоненты, статика и готовые сборки.
- `api/` — HTTP-маршруты и проверки доступа.
- `backend/` — сервисы, работа с БД, платежи и создание приложений.
- `bot/` — Telegram-бот, меню, обработчики и middleware.
- `tools/` — проверки исходников и сборок.
- `docs/` — описание структуры и инструкции запуска.
- `entry_*.py` и `manage.py` — точки запуска, совместимые с существующими командами.

Структура каталогов: [docs/structure.md](docs/structure.md).
Запуск процессов: [docs/services.md](docs/services.md).

## Сборка интерфейсов

```powershell
cd frontend
npm ci
npm run build
```

Все приложения используют один npm workspace и общий `package-lock.json`.
Для локальной разработки доступны `npm run dev:admin`, `npm run dev:cabinet`,
`npm run dev:miniapp` и `npm run dev:landing`.

## Базовая безопасность

- Mini App API проверяет подпись `initData` от Telegram и ограничивает срок ее жизни.
- Cabinet использует короткоживущий access token и refresh token в `httpOnly` cookie.
- Admin использует серверные сессии, обязательную двухфакторную проверку и ограничение попыток входа.
- Bot API теперь принимает только отдельный `BOT_API_TOKEN`; fallback на `SECRET_KEY` убран.
- Для всех HTTP-приложений включены `TrustedHostMiddleware` и базовые security headers.

## Что нужно настроить в production

- `TRUSTED_HOSTS` - реальные домены приложения.
- `API_CORS_ORIGINS` - только допустимые frontend origin'ы.
- `UVICORN_FORWARDED_ALLOW_IPS` - IP вашего reverse proxy.
- HTTPS на уровне reverse proxy, чтобы `secure` cookie и HSTS работали корректно.
