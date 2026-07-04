import asyncio
import aiohttp
from typing import Optional, Dict, Any
from backend.core.config import settings
from backend.core.logger_config import logger


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
            raise ValueError("PLATEGA credentials are missing")
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
        url = f"{self.BASE_URL}{path}"
        headers = self._auth_headers()
        extra_headers = kwargs.pop("headers", None)
        if extra_headers:
            headers.update(extra_headers)

        attempts = 3
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            session = await self._get_session()
            try:
                async with session.request(method, url, headers=headers, **kwargs) as resp:
                    try:
                        data = await resp.json()
                    except aiohttp.ContentTypeError:
                        data = {"error": await resp.text()}
                    data["http_status"] = resp.status
                    if resp.status >= 400 and "error" not in data:
                        data["error"] = f"HTTP {resp.status}"
                    return data
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "[platega] request retry method=%s url=%s attempt=%s/%s err=%s",
                    method,
                    url,
                    attempt,
                    attempts,
                    exc,
                )
                if attempt == attempts:
                    break
                await asyncio.sleep(0.5 * attempt)

        raise RuntimeError(f"Platega request failed: {last_exc}")

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
            "paymentDetails": {"amount": float(amount), "currency": currency},
        }
        if description:
            body["description"] = description
        if return_url:
            body["return"] = return_url
        if failed_url:
            body["failedUrl"] = failed_url
        if payload:
            body["payload"] = payload

        result = await self._request("POST", self.CREATE_ENDPOINT, json=body)

        if "error" in result:
            raise ValueError(f"Platega API error: {result['error']}")

        if "transactionId" not in result:
            raise ValueError(f"Platega API did not return transactionId: {result}")

        result["id"] = result["transactionId"]
        return result

    async def get_status(self, transaction_id: str) -> Dict[str, Any]:
        path = self.STATUS_ENDPOINT.format(id=transaction_id)
        result = await self._request("GET", path)
        if "error" in result:
            raise ValueError(f"Platega API error: {result['error']}")
        return result

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None 

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
