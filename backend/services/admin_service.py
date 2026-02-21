from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.admin_repository import AdminRepository
from backend.repositories.server_repository import ServerRepository
from backend.services.exceptions import AdminPermissionDenied, ServerNotFound

from backend.core.loader import settings


class AdminService:
    def __init__(self, session: AsyncSession, xray_agent_token: str | None = None):
        self.session = session
        self.admin_repo = AdminRepository(session)
        self.server_repo = ServerRepository(session)
        self.XRAY_AGENT_TOKEN = settings.XRAY_AUTH

    async def ensure_admin(self, user_id: int) -> None:
        admin = await self.admin_repo.get_by_id(user_id)
        if not admin or not admin.is_active:
            raise AdminPermissionDenied("Admin only")

    async def list_servers(self):
        return await self.server_repo.list_all()

    def _normalize_agent_base(self, endpoint: str) -> str:
        endpoint = (endpoint or "").strip()
        if not endpoint:
            raise ServerNotFound("server grpc_endpoint is empty")

        parsed = urlparse(endpoint)
        if not parsed.scheme:
            return f"http://{endpoint}"
        return endpoint

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.XRAY_AGENT_TOKEN:
            h["Authorization"] = f"Bearer {self.XRAY_AGENT_TOKEN}"
        return h

    async def _get_json(self, url: str) -> dict[str, Any]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as http:
            async with http.get(url, headers=self._headers()) as resp:
                raw = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"agent GET failed status={resp.status} url={url} body={raw[:800]}")
                try:
                    return await resp.json()
                except Exception:
                    raise RuntimeError(f"agent returned non-json url={url} body={raw[:800]}")

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as http:
            async with http.post(url, json=payload, headers=self._headers()) as resp:
                raw = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"agent POST failed status={resp.status} url={url} body={raw[:800]}")
                try:
                    return await resp.json()
                except Exception:
                    raise RuntimeError(f"agent returned non-json url={url} body={raw[:800]}")

    async def _get_server(self, server_id: int):
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise ServerNotFound("server not found")
        return server

    async def get_server_stats(self, server_id: int) -> dict[str, Any]:
        server = await self._get_server(server_id)
        base = self._normalize_agent_base(server.grpc_endpoint) 
        return await self._get_json(f"{base}/stats")

    async def get_server_health(self, server_id: int) -> dict[str, Any]:
        server = await self._get_server(server_id)
        base = self._normalize_agent_base(server.grpc_endpoint)
        return await self._get_json(f"{base}/health")

    async def resync_server(self, server_id: int) -> dict[str, Any]:
        server = await self._get_server(server_id)
        base = self._normalize_agent_base(server.grpc_endpoint)
        return await self._post_json(f"{base}/resync", payload={})
