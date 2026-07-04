import aiohttp
from typing import Optional, Dict, Any, List
from enum import Enum
from backend.core.config import settings


class CurrencyType(str, Enum):
    CRYPTO = "crypto"
    FIAT = "fiat"


class CryptoPayAPI:
    BASE_URL_MAINNET = "https://pay.crypt.bot/api"
    BASE_URL_TESTNET = "https://testnet-pay.crypt.bot/api"

    def __init__(self, *, testnet: bool = False, timeout: int = 20):
        self.api_token = settings.CRYPTOBOT_SECRET
        self.base_url = self.BASE_URL_TESTNET if testnet else self.BASE_URL_MAINNET
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Crypto-Pay-API-Token": self.api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with session.request(method, url, headers=headers, **kwargs) as resp:
            try:
                data = await resp.json()
            except aiohttp.ContentTypeError:
                text = await resp.text()
                raise ValueError(f"CryptoPay API returned non-JSON response: {text}")

            if not data.get("ok", False):
                raise ValueError(f"CryptoPay API error: {data.get('error')}")
            return data.get("result", {})

    async def create_invoice(
        self,
        amount: float,
        currency_type: CurrencyType = CurrencyType.CRYPTO,
        asset: Optional[str] = None,
        fiat: Optional[str] = None,
        accepted_assets: Optional[List[str]] = None,
        description: Optional[str] = None,
        hidden_message: Optional[str] = None,
        swap_to: Optional[str] = None,
        payload: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "amount": str(amount),
            "currency_type": currency_type.value,
        }

        if currency_type == CurrencyType.CRYPTO:
            if not asset:
                raise ValueError("asset must be specified for CRYPTO invoices")
            body["asset"] = asset
        else:
            if not fiat:
                raise ValueError("fiat must be specified for FIAT invoices")
            body["fiat"] = fiat
            if accepted_assets:
                body["accepted_assets"] = ",".join(accepted_assets)

        if description:
            body["description"] = description
        if hidden_message:
            body["hidden_message"] = hidden_message
        if swap_to:
            body["swap_to"] = swap_to
        if payload:
            body["payload"] = payload
        if expires_in:
            body["expires_in"] = expires_in

        return await self._request("POST", "createInvoice", json=body)

    async def get_invoice_status(self, invoice_id: int) -> Dict[str, Any]:
        params = {"invoice_ids": str(invoice_id)}
        invoices = await self._request("GET", "getInvoices", params=params)
        if isinstance(invoices, list) and invoices:
            first = invoices[0]
            return first if isinstance(first, dict) else {}
        if isinstance(invoices, dict):
            for key in ("items", "invoices", "data", "result"):
                value = invoices.get(key)
                if isinstance(value, list) and value:
                    first = value[0]
                    return first if isinstance(first, dict) else {}
            if "invoice_id" in invoices or "status" in invoices:
                return invoices
        return {}

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
