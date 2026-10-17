# Public catalog

Production requests `https://api.lunet.pro/api/public/catalog` with `credentials: omit`. The public catalog requires no access token or cookies. The API must allow the landing origin via `API_CORS_ORIGINS` (including `https://lunet.pro` and `https://www.lunet.pro`).

On localhost/127.0.0.1/IPv6 loopback, requests use `/api/public/catalog` and the Vite development proxy. To override the API origin at build time, set `VITE_PUBLIC_API_BASE_URL`, e.g. `https://api.example.test`. An explicit empty value selects a same-origin API proxy. Set an origin without `/api` suffix.

`/catalog.json` remains an optional same-origin fallback. It is served by `backend.apps.landing` but may not exist on a static deployment. It is not required when the public API responds successfully.

After building, deploy the updated `frontend/build/landing` HTML and assets together. The API domain change is baked into the new bundle; old deployed JavaScript will keep using the old address until updated.
