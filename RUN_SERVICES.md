# Run Services

## Bootstrap

```powershell
python manage.py bootstrap
```

## Single service

```powershell
python manage.py run landing
python manage.py run miniapp
python manage.py run cabinet
python manage.py run admin
python manage.py run api
python manage.py run bot
```

## Legacy entrypoints

Они сохранены для совместимости, но теперь являются тонкими обертками над `backend/apps/*`:

```powershell
python entry_landing.py
python entry_miniapp.py
python entry_cabinet.py
python entry_admin_frontend.py
python entry_api.py
python entry_bot.py
```

## Recommended production notes

- Запускайте сервисы за reverse proxy.
- Задайте `TRUSTED_HOSTS`, `API_CORS_ORIGINS` и `UVICORN_FORWARDED_ALLOW_IPS`.
- Не используйте `SECRET_KEY` вместо `BOT_API_TOKEN`: этот fallback удален.
