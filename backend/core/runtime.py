from __future__ import annotations

import asyncio
import os

import uvicorn

from backend.core.config import settings


def run_uvicorn(import_path: str, *, port_env: str, default_port: int) -> None:
    uvicorn.run(
        import_path,
        host=settings.UVICORN_HOST,
        port=int(os.getenv(port_env, str(default_port))),
        reload=settings.UVICORN_RELOAD,
        proxy_headers=True,
        forwarded_allow_ips=settings.UVICORN_FORWARDED_ALLOW_IPS,
        factory=":create_app" in import_path,
    )


def run_async(entrypoint) -> None:
    asyncio.run(entrypoint())
