import aiohttp
from typing import Optional, Dict, Any
from server.core.loader import settings


class PlategaPaymentAPI:

    BASE_URL = "https://app.platega.io"
    CREATE_ENDPOINT = "/transaction/process"
    STATUS_ENDPOINT = "/transaction/{id}"

    def __init__(
        self,
        merchant_id: Optional[str] = None,
        secret: Optional[str] = None,
        *,
        timeout_total: int = 20,
    ) -> None:
        self.merchant_id = merchant_id or settings.PLATEGA_MERCHANT_ID
        self.secret = secret or settings.PLATEGA_SECRET
        if not self.merchant_id or not self.secret:
            raise ValueError("PLATEGA credentials are missing: set PLATEGA_MERCHANT_ID and PLATEGA_SECRET")

        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=timeout_total)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:

        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"

        headers = self._auth_headers()
        extra_headers = kwargs.pop("headers", None)
        if extra_headers:
            headers.update(extra_headers)

        async with session.request(method, url, headers=headers, **kwargs) as resp:
            try:
                data = await resp.json()
            except aiohttp.ContentTypeError:
                data = {"error": await resp.text()}
            data["http_status"] = resp.status
            if resp.status >= 400 and "error" not in data:
                data["error"] = f"HTTP {resp.status}"
            return data

    async def create_payment(
        self,
        *,
        amount: float,
        currency: str = "RUB",
        payment_method: int = 2,
        description: Optional[str] = None,
        return_url: Optional[str] = None,
        failed_url: Optional[str] = None,
        payload: Optional[str] = None,
    ) -> Dict[str, Any]:

        body: Dict[str, Any] = {
            "paymentMethod": payment_method,
            "paymentDetails": {
                "amount": float(amount),
                "currency": currency,
            },
        }
        if description:
            body["description"] = description
        if return_url:
            body["return"] = return_url
        if failed_url:
            body["failedUrl"] = failed_url
        if payload:
            body["payload"] = payload

        return await self._request("POST", self.CREATE_ENDPOINT, json=body)

    async def get_status(self, transaction_id: str) -> Dict[str, Any]:

        path = self.STATUS_ENDPOINT.format(id=transaction_id)
        return await self._request("GET", path)

    async def close(self) -> None:

        if self._session and not self._session.closed:
            await self._session.close()
