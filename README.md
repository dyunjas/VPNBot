# Frontend/API Sync Notes

## Entry points
- `/admin` -> admin panel
- `/cabinet` -> web cabinet (serves existing mini-app UI)
- `/cabinet/login` -> web login by one-time code
- `/tg-app` -> Telegram mini-app entry redirect to `/miniapp/`
- `/` -> public landing
- Telegram -> Web bridge: mini-app button opens `/cabinet?initData=...`

## Backend SSOT inventory
- Full API inventory: [docs/api_schema.json](/c:/Users/dyunj/VPNBot/docs/api_schema.json)
- Admin frontend now uses only endpoints connected in `api/admin/endpoints.py`.

## Removed as dead admin feature
- Removed admin `servers` UI route and page:
  - deleted `/admin/servers` page mapping
  - deleted `app/admin_frontend/servers.html`
  - deleted `app/admin_frontend/js/pages/servers.js`
- Reason: `servers` router is not included in active `/admin-api` aggregate router.

## Admin UI updates
- Added theme switch support (light/dark) in shared layout via `localStorage` key `admin_theme`.
- Navigation excludes sections without active API wiring.

## Acceptance behavior
- UI surface only includes backend-backed sections.
- If backend endpoint/field is removed, related UI should be removed/hidden in follow-up sync; no fake data paths remain in removed sections.

## Important auth note
- Added backend cabinet auth and API endpoints under `/cabinet-api`.
- Login methods:
  - email + code
  - telegram id + code (code delivered by bot)
- Session:
  - short-lived access token in browser storage (`cabinet_access_token`)
  - refresh token in httpOnly cookie
  - refresh endpoint: `POST /cabinet-api/auth/refresh`
  - logout endpoint: `POST /cabinet-api/auth/logout`
- SMTP env required for email-code flow: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`.
- Current DB schema still requires `tg_id` for registration (enforced at API level).
