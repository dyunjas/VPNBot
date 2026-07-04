from __future__ import annotations

from typing import Any

import aiohttp

from backend.core.config import settings
from backend.core.maintenance import MAINTENANCE_MESSAGE, is_maintenance_enabled
from backend.services.exceptions import (
    BannedUser,
    InsufficientBalance,
    MaintenanceModeError,
    NotEnoughReferralBalance,
    PaymentNotConfirmed,
    PlanNotFound,
    PromocodeAlreadyUsed,
    PromocodeExhausted,
    PromocodeNotFound,
    PurchaseInProgress,
    SubscriptionNotFound,
    TooEarlyToRenew,
    TransactionNotFound,
    UserNotFound,
)


class BotApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or settings.API_BASE_URL or "http://127.0.0.1:8004").rstrip("/")
        self.token = (token or settings.BOT_API_TOKEN or settings.SECRET_KEY or "").strip()
        self._session: aiohttp.ClientSession | None = None
        self._timeout = aiohttp.ClientTimeout(total=20, connect=5, sock_connect=5, sock_read=15)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Bot-Token"] = self.token
        return headers

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{path}"

    @staticmethod
    def _detail_text(payload: Any) -> str:
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if detail is not None:
                return str(detail)
        return str(payload or "")

    async def _request_json(self, method: str, path: str, *, json: dict | None = None) -> Any:
        if is_maintenance_enabled():
            raise MaintenanceModeError(MAINTENANCE_MESSAGE)
        session = await self._get_session()
        try:
            async with session.request(method, self._url(path), json=json, headers=self._headers()) as resp:
                try:
                    payload = await resp.json(content_type=None)
                except Exception:
                    payload = await resp.text()

                if resp.status >= 400:
                    raise self._map_error(resp.status, payload)
                return payload
        except MaintenanceModeError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise MaintenanceModeError(MAINTENANCE_MESSAGE) from exc

    @staticmethod
    def _map_error(status: int, payload: Any) -> Exception:
        detail = BotApiClient._detail_text(payload)
        message = detail or "API error"
        if status == 503:
            return MaintenanceModeError(MAINTENANCE_MESSAGE)
        if status == 401:
            return PermissionError(message)
        if status == 402:
            if "referral" in message.lower():
                return NotEnoughReferralBalance(message)
            return InsufficientBalance(message)
        if status == 403:
            if "banned" in message.lower():
                return BannedUser(message)
            return PermissionError(message)
        if status == 404:
            text = message.lower()
            if "subscription" in text:
                return SubscriptionNotFound(message)
            if "plan" in text:
                return PlanNotFound(message)
            if "transaction" in text:
                return TransactionNotFound(message)
            if "promocode" in text:
                return PromocodeNotFound(message)
            if "user" in text:
                return UserNotFound(message)
            return LookupError(message)
        if status == 409:
            text = message.lower()
            if "email" in text:
                return ValueError(message)
            if "too early" in text or "renew" in text:
                return TooEarlyToRenew(message)
            if "promocode" in text and "used" in text:
                return PromocodeAlreadyUsed(message)
            if "promocode" in text and ("exhausted" in text or "limit" in text):
                return PromocodeExhausted(message)
            if (
                "payment" in text
                or "confirm" in text
                or "not approved" in text
                or "подтвержден" in text
                or "подтверд" in text
                or "платеж" in text
            ):
                return PaymentNotConfirmed(message)
            return PurchaseInProgress(message)
        return RuntimeError(message)

    async def get_user_by_tg_id(self, tg_id: int) -> dict[str, Any]:
        return await self._request_json("GET", f"/api/users/by-tg/{tg_id}")

    async def ensure_user(self, *, tg_id: int, username: str | None = None) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/api/users/ensure",
            json={"tg_id": tg_id, "username": username},
        )

    async def update_username(self, *, user_id: int, username: str | None) -> dict[str, Any]:
        return await self._request_json(
            "PATCH",
            f"/api/users/{user_id}/username",
            json={"username": username},
        )

    async def update_email(self, *, user_id: int, email: str | None) -> dict[str, Any]:
        return await self._request_json(
            "PATCH",
            f"/api/users/{user_id}/email",
            json={"email": email},
        )

    async def attach_referrer(self, *, user_id: int, referrer_tg_id: int) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/{user_id}/referrer",
            json={"referrer_tg_id": referrer_tg_id},
        )

    async def attach_partner(self, *, user_id: int, code: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/{user_id}/partner",
            json={"code": code},
        )

    async def activate_trial(self, *, user_id: int) -> dict[str, Any]:
        return await self._request_json("POST", f"/api/users/{user_id}/trial")

    async def get_profile(self, *, tg_id: int) -> dict[str, Any]:
        return await self._request_json("GET", f"/api/users/by-tg/{tg_id}/profile")

    async def list_transactions(self, *, tg_id: int) -> list[dict[str, Any]]:
        data = await self._request_json("GET", f"/api/users/by-tg/{tg_id}/transactions")
        return list(data.get("items") or [])

    async def get_transaction(self, *, tg_id: int, transaction_id: int) -> dict[str, Any]:
        return await self._request_json("GET", f"/api/users/by-tg/{tg_id}/transactions/{transaction_id}")

    async def get_referral_info(self, *, tg_id: int) -> dict[str, Any]:
        return await self._request_json("GET", f"/api/users/by-tg/{tg_id}/referral")

    async def create_withdrawal(self, *, tg_id: int, amount: int, method: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/withdrawals",
            json={"amount": amount, "method": method},
        )

    async def list_withdrawals(self, *, tg_id: int) -> list[dict[str, Any]]:
        data = await self._request_json("GET", f"/api/users/by-tg/{tg_id}/withdrawals")
        return list(data.get("items") or [])

    async def list_plans(self, *, tg_id: int) -> list[dict[str, Any]]:
        data = await self._request_json("GET", f"/api/users/by-tg/{tg_id}/plans")
        return list(data.get("items") or [])

    async def get_subscription(self, *, tg_id: int) -> dict[str, Any]:
        return await self._request_json("GET", f"/api/users/by-tg/{tg_id}/subscription")

    async def buy_subscription(self, *, tg_id: int, plan_id: int, auto_renew: bool = True) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/subscription/buy",
            json={"plan_id": plan_id, "auto_renew": auto_renew},
        )

    async def buy_traffic(self, *, tg_id: int, gb: int) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/subscription/traffic",
            json={"gb": gb},
        )

    async def set_auto_renew(self, *, tg_id: int, auto_renew: bool) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/subscription/auto-renew",
            json={"auto_renew": auto_renew},
        )

    async def get_subscription_url(self, *, tg_id: int) -> dict[str, Any]:
        return await self._request_json("GET", f"/api/users/by-tg/{tg_id}/subscription/url")

    async def get_devices(self, *, tg_id: int) -> list[dict[str, Any]]:
        data = await self._request_json("GET", f"/api/users/by-tg/{tg_id}/devices")
        return list(data.get("items") or [])

    async def delete_device(self, *, tg_id: int, device_id: int) -> dict[str, Any]:
        return await self._request_json(
            "DELETE",
            f"/api/users/by-tg/{tg_id}/devices/{device_id}",
        )

    async def activate_promocode(self, *, tg_id: int, code: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/promocode",
            json={"code": code},
        )

    async def create_platega_payment(self, *, tg_id: int, amount: float, payment_method: int, description: str | None = None, return_url: str | None = None, failed_url: str | None = None) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/payments/platega",
            json={
                "amount": amount,
                "payment_method": payment_method,
                "description": description,
                "return_url": return_url,
                "failed_url": failed_url,
            },
        )

    async def confirm_platega_payment(self, *, tg_id: int, provider_transaction_id: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/payments/platega/confirm",
            json={"provider_transaction_id": provider_transaction_id},
        )

    async def create_crypto_invoice(self, *, tg_id: int, amount_rub: int, asset: str = "USDT", description: str | None = None, expires_in: int | None = 900) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/payments/crypto",
            json={
                "amount": amount_rub,
                "asset": asset,
                "description": description,
                "expires_in": expires_in,
            },
        )

    async def confirm_crypto_payment(self, *, tg_id: int, invoice_id: int) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/payments/crypto/confirm",
            json={"invoice_id": invoice_id},
        )

    async def create_pally_payment(self, *, tg_id: int, amount: float, description: str | None = None, return_url: str | None = None, failed_url: str | None = None, ttl: int = 600) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/payments/pally",
            json={
                "amount": amount,
                "description": description,
                "return_url": return_url,
                "failed_url": failed_url,
                "ttl": ttl,
            },
        )

    async def confirm_pally_payment(self, *, tg_id: int, provider_transaction_id: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/api/users/by-tg/{tg_id}/payments/pally/confirm",
            json={"provider_transaction_id": provider_transaction_id},
        )
