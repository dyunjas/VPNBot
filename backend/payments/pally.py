from __future__ import annotations

from collections import OrderedDict
from typing import Optional, Dict, Any

import aiohttp

from backend.core.config import settings


class PallyPaymentAPI:
    CREATE_URL = "https://pal24.pro/api/v1/bill/create"
    STATUS_URL = "https://pal24.pro/api/v1/bill/status"

    def __init__(
        self,
        *,
        api_token: Optional[str] = None,
        shop_id: Optional[str] = None,
        success_url: Optional[str] = None,
        fail_url: Optional[str] = None,
        timeout_total: int = 20,
    ) -> None:
        self.api_token = api_token or settings.PALLY_API_TOKEN
        self.shop_id = shop_id or settings.PALLY_SHOP_ID
        self.success_url = success_url or settings.PALLY_SUCCESS_URL
        self.fail_url = fail_url or settings.PALLY_FAIL_URL

        if not self.api_token or not self.shop_id:
            raise ValueError("PALLY credentials are missing")

        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=timeout_total)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _parse_response(self, resp: aiohttp.ClientResponse) -> Dict[str, Any]:
        try:
            data = await resp.json()
        except aiohttp.ContentTypeError:
            data = {"error": await resp.text()}

        data["http_status"] = resp.status
        if resp.status >= 400 and "error" not in data:
            data["error"] = f"HTTP {resp.status}"
        return data

    async def create_invoice(
        self,
        *,
        amount: float,
        order_id: str,
        description: str,
        success_url: Optional[str] = None,
        fail_url: Optional[str] = None,
        ttl: int = 600,
    ) -> Dict[str, Any]:
        data = OrderedDict(
            [
                ("amount", round(float(amount), 2)),
                ("shop_id", self.shop_id),
                ("order_id", str(order_id)),
                ("description", description),
                ("type", "normal"),
                ("currency_in", "RUB"),
                ("name", "Lunet VPN"),
                ("ttl", int(ttl)),
            ]
        )

        final_success = success_url or self.success_url
        final_fail = fail_url or self.fail_url
        if final_success:
            data["success_url"] = final_success
        if final_fail:
            data["fail_url"] = final_fail

        session = await self._get_session()
        async with session.post(self.CREATE_URL, json=data, headers=self._auth_headers()) as resp:
            return await self._parse_response(resp)

    async def get_status(self, bill_id: str) -> Dict[str, Any]:
        session = await self._get_session()
        url = f"{self.STATUS_URL}?id={bill_id}"
        async with session.get(url, headers=self._auth_headers()) as resp:
            return await self._parse_response(resp)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
