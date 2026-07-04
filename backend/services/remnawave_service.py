from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from datetime import timedelta
from decimal import Decimal
import json
from typing import Any
from urllib.parse import urlparse

import aiohttp

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.repositories.subscription_repository import SubscriptionRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.subscription_topup_repository import SubscriptionTopupRepository


class RemnaWaveService:
    def __init__(self, session):
        self.session = session
        self.user_repo = UserRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.topup_repo = SubscriptionTopupRepository(session)
        self.base_url = (settings.REMNAWAVE_BASE_URL or "").rstrip("/")
        self.token = (settings.REMNAWAVE_API_TOKEN or "").strip()
        raw_cookies = (
            settings.REMNAWAVE_COOKIES
            or getattr(settings, "COOKIES", None)
            or ""
        )
        self.cookies = self._parse_cookies(raw_cookies)
        self.active_internal_squads = self._parse_uuid_list(
            settings.REMNAWAVE_ACTIVE_INTERNAL_SQUADS or ""
        )
        self.upsert_path = (settings.REMNAWAVE_UPSERT_PATH or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if self.cookies:
            headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
        return headers

    @staticmethod
    def _parse_cookies(raw: str | None) -> dict[str, str]:
        value = (raw or "").strip()
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except Exception:
            logger.warning("[remnawave] invalid REMNAWAVE_COOKIES JSON; cookies disabled")
            return {}
        if not isinstance(parsed, dict):
            logger.warning("[remnawave] REMNAWAVE_COOKIES must be JSON object; cookies disabled")
            return {}
        out: dict[str, str] = {}
        for k, v in parsed.items():
            if k is None or v is None:
                continue
            out[str(k)] = str(v)
        return out

    @staticmethod
    def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in payload.items():
            if v is None:
                continue
            if k == "activeInternalSquads" and isinstance(v, list) and not v:
                continue
            out[k] = v
        return out

    @staticmethod
    def _parse_uuid_list(raw: str | None) -> list[str]:
        value = (raw or "").strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except Exception:
            logger.warning("[remnawave] invalid REMNAWAVE_ACTIVE_INTERNAL_SQUADS JSON; squads disabled")
            return []
        if not isinstance(parsed, list):
            logger.warning("[remnawave] REMNAWAVE_ACTIVE_INTERNAL_SQUADS must be JSON array; squads disabled")
            return []
        out: list[str] = []
        for item in parsed:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out

    @staticmethod
    def _sanitize_username(raw: str) -> str:
        allowed = []
        for ch in raw:
            if ch.isalnum() or ch in ("_", "-"):
                allowed.append(ch)
            else:
                allowed.append("_")
        username = "".join(allowed).strip("_-")
        if len(username) < 3:
            username = f"user_{username}" if username else "user_default"
        return username[:36]

    def _build_username(self, user) -> str:
        base = getattr(user, "username", None) or f"user_{getattr(user, 'tg_id', None) or getattr(user, 'id', 0)}"
        return self._sanitize_username(str(base))

    def _extract_first_link(self, data: Any) -> str | None:
        candidates = (
            "subscription_url",
            "subscriptionUrl",
            "sub_url",
            "subUrl",
            "subscription_link",
            "subscriptionLink",
            "link",
            "url",
        )
        if isinstance(data, dict):
            for key in candidates:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in data.values():
                found = self._extract_first_link(value)
                if found:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = self._extract_first_link(item)
                if found:
                    return found
        return None

    @staticmethod
    def _unwrap_response(data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        response = data.get("response")
        if response is None:
            return data
        return response

    def _extract_remote_user_id(self, data: Any) -> str | int | None:
        if not isinstance(data, dict):
            return None
        for key in ("id", "uuid", "user_id", "userId"):
            value = data.get(key)
            if value not in (None, ""):
                return value
        nested = data.get("user")
        if isinstance(nested, dict):
            for key in ("id", "uuid", "user_id", "userId"):
                value = nested.get(key)
                if value not in (None, ""):
                    return value
        return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _status_is_active(subscription) -> bool:
        if not subscription:
            return False
        status = getattr(subscription, "status", None)
        raw = getattr(status, "value", status)
        return str(raw or "").lower() == "active"

    def _extract_remote_user_uuid(self, data: Any) -> str | None:
        if not isinstance(data, dict):
            return None
        value = data.get("uuid")
        if isinstance(value, str) and value.strip():
            return value.strip()
        nested = data.get("user")
        if isinstance(nested, dict):
            value = nested.get("uuid")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _extract_remote_ref(self, data: Any) -> tuple[str | int | None, str | None]:
        return self._extract_remote_user_id(data), self._extract_remote_user_uuid(data)

    @staticmethod
    def _extract_subscription_token_from_url(url: str | None) -> str | None:
        if not isinstance(url, str):
            return None
        value = url.strip()
        if not value:
            return None
        try:
            path = (urlparse(value).path or "").strip("/")
            if not path:
                return None
            token = path.split("/")[-1].strip()
            return token or None
        except Exception:
            return None

    async def _persist_subscription_token(self, *, subscription, subscription_url: str | None) -> None:
        if not subscription or not getattr(subscription, "id", None):
            return
        token = self._extract_subscription_token_from_url(subscription_url)
        if not token:
            return
        current = getattr(subscription, "subscription_token", None)
        if current == token:
            return
        try:
            await self.sub_repo.set_subscription_token(subscription_id=subscription.id, token=token)
            await self.session.commit()
            subscription.subscription_token = token
        except Exception:
            logger.exception("[remnawave] persist subscription token failed subscription_id=%s", getattr(subscription, "id", None))

    def _iso_or_none(self, dt) -> str | None:
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        # Remnawave validator works reliably with strict UTC Z format.
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @staticmethod
    def _parse_iso_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _normalize_expire_at(self, expire_at: str | None) -> str:
        now = datetime.now(timezone.utc)
        min_expire = now + timedelta(minutes=5)
        dt = self._parse_iso_dt(expire_at)
        if not dt or dt <= min_expire:
            dt = now + timedelta(days=30)
        return self._iso_or_none(dt) or (now + timedelta(days=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    async def _calculate_traffic_limit_bytes(self, *, user, subscription) -> int:
        stored = max(0, int(getattr(user, "traffic_limit_bytes", 0) or 0))
        if not subscription:
            return stored

        topup_gb = Decimal(0)
        try:
            topup_gb = await self.topup_repo.sum_gb(subscription_id=subscription.id)
        except Exception:
            topup_gb = Decimal(0)

        plan_gb = Decimal(0)
        try:
            plan_id = getattr(subscription, "plan_id", None)
            if plan_id is not None:
                plan = await self.sub_repo.get_plan_by_id(int(plan_id))
                plan_gb = Decimal(getattr(plan, "gb_limit", 0) or 0)
        except Exception:
            plan_gb = Decimal(0)

        calculated = max(0, int((plan_gb + Decimal(topup_gb or 0)) * Decimal(1024**3)))
        if calculated != stored:
            await self.user_repo.set_traffic_limit_bytes(
                user_id=user.id,
                traffic_limit_bytes=calculated,
            )
            user.traffic_limit_bytes = calculated
        return calculated

    async def _desired_user_status(self, *, user, subscription) -> str:
        if bool(getattr(user, "banned", False)):
            return "DISABLED"
        if subscription and self._status_is_active(subscription):
            expires_at = getattr(subscription, "current_period_end", None)
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at > datetime.now(timezone.utc):
                    return "ACTIVE"
        return "DISABLED"

    async def _build_payload(self, user, subscription) -> dict[str, Any]:
        traffic_limit_bytes = await self._calculate_traffic_limit_bytes(
            user=user,
            subscription=subscription,
        )
        desired_status = await self._desired_user_status(user=user, subscription=subscription)
        raw_expire_at = self._iso_or_none(getattr(subscription, "current_period_end", None)) if subscription else None
        expire_at = self._normalize_expire_at(raw_expire_at) if desired_status == "ACTIVE" else None

        return {
            "username": self._build_username(user),
            "expireAt": expire_at,
            "status": desired_status,
            "trafficLimitBytes": max(0, int(traffic_limit_bytes)),
            "trafficLimitStrategy": "NO_RESET",
            "hwidDeviceLimit": 3,
            "telegramId": int(getattr(user, "tg_id", 0) or 0) or None,
            "email": getattr(user, "email", None),
            "description": f"Lunet user_id={getattr(user, 'id', None)}",
            "activeInternalSquads": self.active_internal_squads,
        }

    async def _build_patch_payload(self, *, user, subscription, remote_uuid: str | None = None) -> dict[str, Any]:
        payload_source = await self._build_payload(user, subscription)
        payload: dict[str, Any] = {
            "uuid": remote_uuid or None,
            "username": None if remote_uuid else payload_source["username"],
            "status": payload_source["status"],
            "trafficLimitBytes": payload_source["trafficLimitBytes"],
            "trafficLimitStrategy": payload_source["trafficLimitStrategy"],
            "hwidDeviceLimit": payload_source["hwidDeviceLimit"],
            "telegramId": payload_source.get("telegramId"),
            "email": payload_source.get("email"),
            "description": payload_source.get("description"),
            "activeInternalSquads": payload_source.get("activeInternalSquads"),
        }
        if payload_source.get("status") == "ACTIVE" and payload_source.get("expireAt"):
            payload["expireAt"] = payload_source["expireAt"]
        return self._compact_payload(payload)

    async def _request_json(self, http: aiohttp.ClientSession, method: str, url: str, **kwargs) -> tuple[int, Any]:
        attempts = 2
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                async with http.request(method, url, headers=self._headers(), **kwargs) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = None
                    return resp.status, data
            except (
                aiohttp.ServerDisconnectedError,
                aiohttp.ClientConnectionError,
                aiohttp.ClientOSError,
                asyncio.TimeoutError,
            ) as e:
                last_exc = e
                logger.warning(
                    "[remnawave] request retry method=%s url=%s attempt=%s/%s err=%s",
                    method,
                    url,
                    attempt,
                    attempts,
                    e,
                )
                if attempt == attempts:
                    break
                await asyncio.sleep(0.35 * attempt)
                continue
        raise RuntimeError(f"remnawave request failed method={method} url={url}: {last_exc}")

    async def _find_remote_user(self, http: aiohttp.ClientSession, user) -> dict[str, Any] | None:
        tg_id = int(getattr(user, "tg_id", 0) or 0)
        if tg_id > 0:
            status, data = await self._request_json(http, "GET", f"{self.base_url}/api/users/by-telegram-id/{tg_id}")
            if status < 400:
                payload = self._unwrap_response(data)
                if isinstance(payload, list) and payload:
                    first = payload[0]
                    if isinstance(first, dict):
                        return first
                if isinstance(payload, dict):
                    return payload

        username = self._build_username(user)
        status, data = await self._request_json(http, "GET", f"{self.base_url}/api/users/by-username/{username}")
        if status < 400:
            payload = self._unwrap_response(data)
            if isinstance(payload, dict):
                return payload
        return None

    async def _resolve_remote_ref(self, *, user, subscription=None) -> tuple[str | int | None, str | None]:
        remote_id = self._coerce_int(getattr(user, "remnawave_user_id", None))
        saved_remote_uuid = (getattr(user, "remnawave_user_uuid", None) or "").strip() or None
        if remote_id is not None:
            remote = await self._fetch_remote_user_by_id(remote_id=remote_id)
            if remote:
                fresh_uuid = self._extract_remote_user_uuid(remote)
                await self._persist_binding(
                    user_id=user.id,
                    remote_id=remote_id,
                    remote_uuid=fresh_uuid,
                    sub_url=self._extract_first_link(remote),
                )
                return remote_id, fresh_uuid

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            existing = await self._find_remote_user(http, user)
        if isinstance(existing, dict):
            found_id = self._extract_remote_user_id(existing)
            found_uuid = self._extract_remote_user_uuid(existing)
            await self._persist_binding(
                user_id=user.id,
                remote_id=found_id,
                remote_uuid=found_uuid,
                sub_url=self._extract_first_link(existing),
            )
            return found_id, found_uuid

        if saved_remote_uuid:
            remote = await self._fetch_remote_user_by_ref(user_ref=saved_remote_uuid)
            if remote:
                found_id = self._extract_remote_user_id(remote)
                found_uuid = self._extract_remote_user_uuid(remote)
                await self._persist_binding(
                    user_id=user.id,
                    remote_id=found_id,
                    remote_uuid=found_uuid,
                    sub_url=self._extract_first_link(remote),
                )
                return found_id, found_uuid

        remote_id, _sub_url, remote_uuid = await self._sync_remote_user(user=user, subscription=subscription)
        await self._persist_binding(
            user_id=user.id,
            remote_id=remote_id,
            remote_uuid=remote_uuid,
            sub_url=getattr(user, "subscription_url", None),
        )
        return remote_id, remote_uuid

    async def _sync_remote_user(self, *, user, subscription) -> tuple[str | int | None, str | None, str | None]:
        payload = await self._build_payload(user, subscription)
        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            create_payload = self._compact_payload(payload)
            if "expireAt" not in create_payload:
                create_payload["expireAt"] = self._normalize_expire_at(None)
            status, data = await self._request_json(
                http,
                "POST",
                f"{self.base_url}/api/users",
                json=create_payload,
            )
            if status < 400:
                remote = self._unwrap_response(data)
                return (
                    self._extract_remote_user_id(remote),
                    self._extract_first_link(remote),
                    self._extract_remote_user_uuid(remote),
                )

            existing = await self._find_remote_user(http, user)
            if existing and existing.get("uuid"):
                patch_payload = await self._build_patch_payload(
                    user=user,
                    subscription=subscription,
                    remote_uuid=existing["uuid"],
                )
                status, data = await self._request_json(http, "PATCH", f"{self.base_url}/api/users", json=patch_payload)
                if status >= 400:
                    minimal_patch_payload = {
                        "uuid": existing["uuid"],
                        "status": payload["status"],
                        "trafficLimitBytes": payload["trafficLimitBytes"],
                        "trafficLimitStrategy": payload["trafficLimitStrategy"],
                    }
                    if payload.get("status") == "ACTIVE" and payload.get("expireAt"):
                        minimal_patch_payload["expireAt"] = payload["expireAt"]
                    status2, data2 = await self._request_json(
                        http,
                        "PATCH",
                        f"{self.base_url}/api/users",
                        json=minimal_patch_payload,
                    )
                    text2 = str(data2 or "")
                    if status2 >= 400 and ("Expiration date cannot be in the past" in text2):
                        minimal_patch_payload["expireAt"] = self._normalize_expire_at(None)
                        status3, data3 = await self._request_json(
                            http,
                            "PATCH",
                            f"{self.base_url}/api/users",
                            json=minimal_patch_payload,
                        )
                        if status3 < 400:
                            data2 = data3
                            status2 = status3
                    if status2 >= 400:
                        raise RuntimeError(
                            f"remnawave patch user failed status={status2} body={data2}"
                        )
                    data = data2
                remote = self._unwrap_response(data)
                return (
                    self._extract_remote_user_id(remote),
                    self._extract_first_link(remote),
                    self._extract_remote_user_uuid(remote),
                )

            raise RuntimeError(f"remnawave create user failed status={status} body={data}")

    async def _persist_binding(self, *, user_id: int, remote_id: str | int | None, remote_uuid: str | None, sub_url: str | None) -> None:
        try:
            await self.user_repo.set_remnawave_binding(
                user_id=user_id,
                remnawave_user_id=self._coerce_int(remote_id),
                remnawave_user_uuid=remote_uuid,
                subscription_url=sub_url,
            )
            await self.session.commit()
        except Exception:
            logger.exception("[remnawave] persist binding failed user_id=%s", user_id)

    async def _fetch_remote_by_id(self, *, remote_id: int) -> tuple[int, str | None, str | None]:
        remote = await self._fetch_remote_user_by_id(remote_id=remote_id)
        if not remote:
            return 404, None, None
        remote_uuid = self._extract_remote_user_uuid(remote)
        sub_url = self._extract_first_link(remote)
        return 200, remote_uuid, sub_url

    async def _fetch_remote_user_by_id(self, *, remote_id: int) -> dict[str, Any] | None:
        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, data = await self._request_json(
                http,
                "GET",
                f"{self.base_url}/api/users/by-id/{remote_id}",
            )
        if status >= 400:
            return None
        remote = self._unwrap_response(data)
        if isinstance(remote, dict):
            return remote
        return None

    async def _fetch_remote_user_by_ref(self, *, user_ref: str) -> dict[str, Any] | None:
        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, data = await self._request_json(
                http,
                "GET",
                f"{self.base_url}/api/users/{user_ref}",
            )
        if status >= 400:
            return None
        remote = self._unwrap_response(data)
        if isinstance(remote, dict):
            return remote
        return None

    async def get_subscription_url(self, *, user, subscription=None) -> str | None:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        saved_remote_id = self._coerce_int(getattr(user, "remnawave_user_id", None))
        if saved_remote_id is not None:
            try:
                status, remote_uuid, sub_url = await self._fetch_remote_by_id(remote_id=saved_remote_id)
                if status < 400 and sub_url:
                    await self._persist_subscription_token(subscription=subscription, subscription_url=sub_url)
                    await self._persist_binding(
                        user_id=user.id,
                        remote_id=saved_remote_id,
                        remote_uuid=remote_uuid,
                        sub_url=sub_url,
                    )
                    return sub_url
            except Exception as e:
                logger.warning(
                    "[remnawave] get by-id failed user_id=%s remote_id=%s err=%s",
                    getattr(user, "id", None),
                    saved_remote_id,
                    e,
                )

        try:
            remote_id, sub_url, remote_uuid = await self._sync_remote_user(user=user, subscription=subscription)
            await self._persist_binding(
                user_id=user.id,
                remote_id=remote_id,
                remote_uuid=remote_uuid,
                sub_url=sub_url,
            )
            if sub_url:
                await self._persist_subscription_token(subscription=subscription, subscription_url=sub_url)
                return sub_url
        except Exception as e:
            logger.warning(
                "[remnawave] sync failed user_id=%s err=%s",
                getattr(user, "id", None),
                e,
            )

        cached_sub_url = (getattr(user, "subscription_url", None) or "").strip()
        if cached_sub_url:
            logger.warning(
                "[remnawave] using cached subscription_url user_id=%s",
                getattr(user, "id", None),
            )
            return cached_sub_url

        logger.warning("[remnawave] subscription_url missing in API response user_id=%s", getattr(user, "id", None))
        return None

    async def get_user_snapshot(self, *, user, subscription=None) -> dict[str, Any] | None:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)
        if remote_id is not None:
            remote = await self._fetch_remote_user_by_id(remote_id=int(remote_id))
            if remote:
                await self._persist_binding(
                    user_id=user.id,
                    remote_id=remote_id,
                    remote_uuid=self._extract_remote_user_uuid(remote) or remote_uuid,
                    sub_url=self._extract_first_link(remote),
                )
                return remote

        if remote_uuid:
            remote = await self._fetch_remote_user_by_ref(user_ref=remote_uuid)
            if remote:
                await self._persist_binding(
                    user_id=user.id,
                    remote_id=self._extract_remote_user_id(remote) or remote_id,
                    remote_uuid=self._extract_remote_user_uuid(remote) or remote_uuid,
                    sub_url=self._extract_first_link(remote),
                )
                return remote

        # Fallback: sync user into panel and fetch by resolved ref.
        synced_id, _sub_url, synced_uuid = await self._sync_remote_user(user=user, subscription=subscription)
        ref = synced_uuid or (str(synced_id) if synced_id is not None else "")
        if not ref:
            return None
        remote = await self._fetch_remote_user_by_ref(user_ref=ref)
        if remote:
            await self._persist_binding(
                user_id=user.id,
                remote_id=synced_id,
                remote_uuid=self._extract_remote_user_uuid(remote) or synced_uuid,
                sub_url=self._extract_first_link(remote),
            )
            return remote
        return None

    async def disable_user_access(self, *, user, subscription=None) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)
        user_uuid = (remote_uuid or "").strip()
        if not user_uuid and remote_id is not None:
            remote = await self._fetch_remote_user_by_id(remote_id=int(remote_id))
            user_uuid = self._extract_remote_user_uuid(remote) if remote else None
        if not user_uuid:
            return False

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, _ = await self._request_json(
                http,
                "POST",
                f"{self.base_url}/api/users/{user_uuid}/actions/disable",
                json={},
            )
        return status < 400

    async def enable_user_access(self, *, user, subscription=None) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)
        user_uuid = (remote_uuid or "").strip()
        if not user_uuid and remote_id is not None:
            remote = await self._fetch_remote_user_by_id(remote_id=int(remote_id))
            user_uuid = self._extract_remote_user_uuid(remote) if remote else None
        if not user_uuid:
            return False

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, _ = await self._request_json(
                http,
                "POST",
                f"{self.base_url}/api/users/{user_uuid}/actions/enable",
                json={},
            )
        return status < 400

    async def delete_user_access(self, *, user, subscription=None) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)
        user_uuid = (remote_uuid or "").strip()
        if not user_uuid and remote_id is not None:
            remote = await self._fetch_remote_user_by_id(remote_id=int(remote_id))
            user_uuid = self._extract_remote_user_uuid(remote) if remote else None
        if not user_uuid:
            return False

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, _ = await self._request_json(
                http,
                "DELETE",
                f"{self.base_url}/api/users/{user_uuid}",
            )
        return status < 400

    async def delete_hwid_device(self, *, user, hwid: str) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        hwid_value = str(hwid or "").strip()
        if not hwid_value:
            return False

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=None)
        user_uuid = (remote_uuid or "").strip()
        if not user_uuid and remote_id is not None:
            status, fetched_uuid, _sub = await self._fetch_remote_by_id(remote_id=int(remote_id))
            if status < 400 and fetched_uuid:
                user_uuid = fetched_uuid
                await self._persist_binding(
                    user_id=user.id,
                    remote_id=remote_id,
                    remote_uuid=fetched_uuid,
                    sub_url=getattr(user, "subscription_url", None),
                )
        if not user_uuid:
            return False

        payload = {
            "userUuid": user_uuid,
            "hwid": hwid_value,
        }
        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, _ = await self._request_json(
                http,
                "POST",
                f"{self.base_url}/api/hwid/devices/delete",
                json=payload,
            )
        return status < 400

    async def reset_user_traffic(self, *, user, subscription=None) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)
        user_uuid = (remote_uuid or "").strip()
        if not user_uuid and remote_id is not None:
            status, fetched_uuid, _sub = await self._fetch_remote_by_id(remote_id=int(remote_id))
            if status < 400 and fetched_uuid:
                user_uuid = fetched_uuid
                await self._persist_binding(
                    user_id=user.id,
                    remote_id=remote_id,
                    remote_uuid=fetched_uuid,
                    sub_url=getattr(user, "subscription_url", None),
                )
        if not user_uuid:
            return False

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, _ = await self._request_json(
                http,
                "POST",
                f"{self.base_url}/api/users/{user_uuid}/actions/reset-traffic",
                json={},
            )
        return status < 400

    async def get_user_hwid_devices(self, *, user) -> list[dict[str, Any]]:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=None)
        user_uuid = (remote_uuid or "").strip()
        if not user_uuid and remote_id is not None:
            status, fetched_uuid, _sub = await self._fetch_remote_by_id(remote_id=int(remote_id))
            if status < 400 and fetched_uuid:
                user_uuid = fetched_uuid
                await self._persist_binding(
                    user_id=user.id,
                    remote_id=remote_id,
                    remote_uuid=fetched_uuid,
                    sub_url=getattr(user, "subscription_url", None),
                )
        if not user_uuid:
            return []

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, data = await self._request_json(
                http,
                "GET",
                f"{self.base_url}/api/hwid/devices/{user_uuid}",
            )
        if status >= 400:
            return []

        payload = self._unwrap_response(data)
        if not isinstance(payload, dict):
            return []
        devices = payload.get("devices")
        if not isinstance(devices, list):
            return []
        return [d for d in devices if isinstance(d, dict)]

    async def sync_subscription_expire_at(self, *, user, subscription) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")
        if not subscription:
            return False

        expire_at = self._iso_or_none(getattr(subscription, "current_period_end", None))
        if not expire_at:
            return False

        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)
        payload: dict[str, Any] = {"expireAt": expire_at}
        if remote_uuid:
            payload["uuid"] = remote_uuid
        else:
            payload["username"] = self._build_username(user)

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, data = await self._request_json(
                http,
                "PATCH",
                f"{self.base_url}/api/users",
                json=payload,
            )
        if status >= 400:
            raise RuntimeError(f"remnawave patch expireAt failed status={status} body={data}")

        remote = self._unwrap_response(data)
        if isinstance(remote, dict):
            await self._persist_binding(
                user_id=user.id,
                remote_id=self._extract_remote_user_id(remote) or remote_id,
                remote_uuid=self._extract_remote_user_uuid(remote) or remote_uuid,
                sub_url=self._extract_first_link(remote),
            )
        return True

    async def sync_local_user(self, *, user, subscription=None) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        remote_id, _sub_url, remote_uuid = await self._sync_remote_user(
            user=user,
            subscription=subscription,
        )
        await self._persist_binding(
            user_id=user.id,
            remote_id=remote_id,
            remote_uuid=remote_uuid,
            sub_url=_sub_url,
        )
        return True

    async def sync_all_local_users(self) -> dict[str, int]:
        users = await self.user_repo.get_all_users()
        now = datetime.now(timezone.utc)
        synced = 0
        failed = 0

        for user in users:
            try:
                subscription = await self.sub_repo.get_active_with_plan(user.id, now=now)
                await self.sync_local_user(user=user, subscription=subscription)
                await self.session.commit()
                synced += 1
            except Exception as e:
                await self.session.rollback()
                failed += 1
                logger.exception(
                    "[remnawave] auto_sync_user_failed user_id=%s tg_id=%s: %s",
                    getattr(user, "id", None),
                    getattr(user, "tg_id", None),
                    e,
                )

        return {
            "total": len(users),
            "synced": synced,
            "failed": failed,
        }

    async def sync_user_traffic_limit(self, *, user, subscription) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")
        if not subscription:
            return False

        payload_source = await self._build_payload(user, subscription)
        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)

        payload: dict[str, Any] = {
            "status": "ACTIVE",
            "trafficLimitBytes": int(payload_source["trafficLimitBytes"]),
            "trafficLimitStrategy": "NO_RESET",
            "expireAt": payload_source["expireAt"],
        }
        if remote_uuid:
            payload["uuid"] = remote_uuid
        else:
            payload["username"] = self._build_username(user)

        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            status, data = await self._request_json(
                http,
                "PATCH",
                f"{self.base_url}/api/users",
                json=payload,
            )
        if status >= 400:
            raise RuntimeError(f"remnawave patch traffic limit failed status={status} body={data}")

        remote = self._unwrap_response(data)
        if isinstance(remote, dict):
            await self._persist_binding(
                user_id=user.id,
                remote_id=self._extract_remote_user_id(remote) or remote_id,
                remote_uuid=self._extract_remote_user_uuid(remote) or remote_uuid,
                sub_url=self._extract_first_link(remote),
            )
        return True

    async def sync_user_state(
        self,
        *,
        user,
        subscription=None,
        status: str = "ACTIVE",
    ) -> bool:
        if not self.enabled:
            raise RuntimeError("remnawave is not configured")

        payload_source = await self._build_payload(user, subscription)
        remote_id, remote_uuid = await self._resolve_remote_ref(user=user, subscription=subscription)

        is_expired_target = str(status).upper() == "EXPIRED"
        near_expire_at = self._iso_or_none(datetime.now(timezone.utc) + timedelta(seconds=40))
        payload: dict[str, Any] = {
            "trafficLimitBytes": int(payload_source["trafficLimitBytes"]),
            "trafficLimitStrategy": "NO_RESET",
            "expireAt": near_expire_at if is_expired_target else payload_source["expireAt"],
            "hwidDeviceLimit": payload_source.get("hwidDeviceLimit"),
        }
        if not is_expired_target:
            payload["status"] = status
        if payload_source.get("activeInternalSquads"):
            payload["activeInternalSquads"] = payload_source["activeInternalSquads"]
        if remote_uuid:
            payload["uuid"] = remote_uuid
        else:
            payload["username"] = self._build_username(user)

        payload = self._compact_payload(payload)
        timeout = aiohttp.ClientTimeout(total=10, connect=4, sock_connect=4, sock_read=6)
        async with aiohttp.ClientSession(timeout=timeout, cookies=self.cookies) as http:
            patch_status, data = await self._request_json(
                http,
                "PATCH",
                f"{self.base_url}/api/users",
                json=payload,
            )

            if patch_status >= 400 and is_expired_target:
                minimal_expired_payload: dict[str, Any] = {
                    "trafficLimitBytes": int(payload_source["trafficLimitBytes"]),
                    "trafficLimitStrategy": "NO_RESET",
                    "expireAt": near_expire_at,
                }
                if remote_uuid:
                    minimal_expired_payload["uuid"] = remote_uuid
                else:
                    minimal_expired_payload["username"] = self._build_username(user)
                patch_status, data = await self._request_json(
                    http,
                    "PATCH",
                    f"{self.base_url}/api/users",
                    json=minimal_expired_payload,
                )
        if patch_status >= 400:
            raise RuntimeError(f"remnawave patch user state failed status={patch_status} body={data}")

        remote = self._unwrap_response(data)
        if isinstance(remote, dict):
            await self._persist_binding(
                user_id=user.id,
                remote_id=self._extract_remote_user_id(remote) or remote_id,
                remote_uuid=self._extract_remote_user_uuid(remote) or remote_uuid,
                sub_url=self._extract_first_link(remote),
            )
        return True
