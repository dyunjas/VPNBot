from __future__ import annotations

import asyncio
import os
import sys

import uvicorn

from backend.core.config import settings


def _configure_event_loop_policy() -> None:
    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def run_uvicorn(import_path: str, *, port_env: str, default_port: int) -> None:
    _configure_event_loop_policy()
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
    _configure_event_loop_policy()
    asyncio.run(entrypoint())
