import base64
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp
from backend.core.logger_config import logger

from backend.repositories.key_repository import KeyRepository
from backend.repositories.server_repository import ServerRepository
from backend.repositories.subscription_repository import SubscriptionRepository
from backend.repositories.user_repository import UserRepository
from backend.services.exceptions import (
    UserNotFound, SubscriptionNotFound, KeyCreationError, TrafficError, ServerNotFound
)
from backend.database.models import KeyStatus


class VPNService:
    def __init__(self, session: AsyncSession, xray_auth_token: str):
        self.session = session
        self.key_repo = KeyRepository(session)
        self.server_repo = ServerRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.user_repo = UserRepository(session)
        self.XRAY_AUTH_TOKEN = xray_auth_token


    def _normalize_agent_base(self, grpc_endpoint: str) -> str:
        grpc_endpoint = (grpc_endpoint or "").strip()
        if not grpc_endpoint:
            return ""
        parsed = urlparse(grpc_endpoint)
        if not parsed.scheme:
            return f"http://{grpc_endpoint}"
        return grpc_endpoint


    async def _create_xray_key(self, user_id: int, server):
        agent_base = self._normalize_agent_base(getattr(server, "grpc_endpoint", "") or "")
        if not agent_base:
            raise Exception("XRAY agent base is empty")

        headers = {
            "Authorization": f"Bearer {self.XRAY_AUTH_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {"email": f"user-{user_id}@lunet"}

        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.post(
                f"{agent_base}/add_user",
                json=payload,
                headers=headers,
            ) as resp:
                data = await resp.json(content_type=None)

        if not data.get("ok"):
            raise Exception(f"XRAY add_user failed: {data}")

        uuid = data["uuid"]

        params = [
            "type=grpc",
            "security=reality",
            "encryption=none",
            f"pbk={server.pbk}",
            f"sni={server.sni}",
            f"fp={server.fp}",
            "serviceName=grpc",
            f"authority={server.sni}",
            "spx=%2F",
        ]

        if server.short_id:
            params.append(f"sid={server.short_id}")

        uri = (
            f"vless://{uuid}@{server.public_host}:{server.port}"
            f"?{'&'.join(params)}#{server.country}"
        )

        return uuid, uri

    async def get_active_subscription(self, user_id: int):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        sub = await self.sub_repo.get_active_with_plan(
            user_id, now=datetime.now(timezone.utc)
        )
        if not sub:
            raise SubscriptionNotFound(f"Active subscription not found for id:{user_id}")
        return sub

    async def get_or_create_keys(self, user_id: int) -> dict[int, str]:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        sub = await self.get_active_subscription(user_id)

        servers = await self.server_repo.list_all()

        existing_keys = await self.key_repo.list_by_user_id(user.id, with_server=False)
        active_keys = [k for k in existing_keys if k.status == KeyStatus.active]

        keys_by_server: dict[int, str] = {
            k.server_id: k.uri for k in active_keys if k.server_id and k.uri
        }

        limit = int(getattr(sub.plan, "key_limit", 0) or 0)

        for server in servers:
            if server.id in keys_by_server:
                continue
            if limit and len(keys_by_server) >= limit:
                break

            try:
                uuid, uri = await self._create_xray_key(user_id=user.id, server=server)

                key = await self.key_repo.create(
                    user_id=user.id,
                    server_id=server.id,
                    uuid=uuid,
                    uri=uri,
                    status=KeyStatus.active,
                    created_at=datetime.now(timezone.utc),
                )

                await self.session.commit()
                await self.session.refresh(key)

                keys_by_server[server.id] = uri

            except Exception as e:
                logger.error(
                    f"[get_or_create_keys] failed user_id={user.id} server_id={server.id}: {e}"
                )
                continue

        return keys_by_server
    
    async def delete_all_user_keys(self, user_id: int) -> int:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        
        deleted = await self.key_repo.delete_all_by_user_id(user_id)
        await self.session.commit()

        return deleted

    async def reset_user_traffic(self, user_id: int) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        servers = await self.server_repo.list_all()
        headers = {"Content-Type": "application/json"}
        if self.XRAY_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {self.XRAY_AUTH_TOKEN}"

        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            for server in servers:
                base = self._normalize_agent_base(getattr(server, "grpc_endpoint", "") or "")
                if not base:
                    continue
                try:
                    async with http.post(
                        f"{base}/reset_user_traffic",
                        headers=headers,
                        params={"user_id": str(user_id)},
                        json={"user_id": user_id},
                    ) as resp:
                        if resp.status >= 400:
                            logger.warning(
                                "[reset_user_traffic] bad response user_id=%s server_id=%s status=%s",
                                user_id,
                                getattr(server, "id", None),
                                resp.status,
                            )
                except Exception as e:
                    logger.warning(
                        "[reset_user_traffic] request failed user_id=%s server_id=%s: %s",
                        user_id,
                        getattr(server, "id", None),
                        e,
                    )


    async def get_keys_for_subscription(self, user_id: int) -> str:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        keys_by_server = await self.get_or_create_keys(user_id)
        uris = list(keys_by_server.values())

        if not uris:
            raise KeyCreationError(f"No keys available for id:{user_id}")

        plain = "\n".join(uris).strip()
        b64 = base64.b64encode(plain.encode("utf-8")).decode("ascii")
        return b64

    async def add_traffic(self, user_id: int, gb: Decimal):
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        sub = await self.get_active_subscription(user_id)
        if gb <= 0:
            raise TrafficError(f"Cannot add non-positive traffic: {gb} GB")
        await self.sub_repo.add_gb_left(sub, gb)
        await self.session.commit()
        await self.session.refresh(sub)
        return sub.gb_left

    async def reissue_keys(self, user_id: int) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        servers = await self.server_repo.list_all()

        keys = await self.key_repo.list_user_keys_by_status(
            user_id=user_id,
            statuses=[KeyStatus.active],
            with_server=True,
        )

        for key in keys:
            server = key.server
            if not server or not server.grpc_endpoint:
                continue

            agent_base = self._normalize_agent_base(server.grpc_endpoint)

            payload = {"email": f"user-{user_id}@lunet"}
            headers = {
                "Authorization": f"Bearer {self.XRAY_AUTH_TOKEN}",
                "Content-Type": "application/json",
            }

            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as http:
                    async with http.post(
                        f"{agent_base}/remove_user",
                        json=payload,
                        headers=headers,
                    ):
                        pass
            except Exception as e:
                logger.error(
                    f"[reissue_keys] XRAY remove_user failed "
                    f"user_id={user_id} server_id={server.id}: {e}"
                )

        await self.key_repo.delete_by_user_id(user_id)
        await self.session.commit()

        created_keys = 0
        for server in servers:
            try:
                uuid, uri = await self._create_xray_key(
                    user_id=user_id,
                    server=server,
                )

                await self.key_repo.create(
                    user_id=user_id,
                    server_id=server.id,
                    uuid=uuid,
                    uri=uri,
                    status=KeyStatus.active,
                    created_at=datetime.now(),
                )
                created_keys += 1
            except Exception as e:
                logger.warning(
                    f"[reissue_keys] create key failed "
                    f"user_id={user_id} server_id={server.id}: {e}"
                )

        if created_keys == 0:
            raise KeyCreationError("Failed to create keys on all servers")

        await self.session.commit()



    async def list_servers(self):
        return await self.server_repo.list_all()

    async def list_active_keys(self, user_id: int):
        return await self.key_repo.list_user_keys_by_status(
            user_id=user_id,
            statuses=[KeyStatus.active],
            with_server=True,
        )

    async def ensure_one_key(self, user_id: int):
        keys = await self.list_active_keys(user_id)
        if keys:
            return False, keys[0]

        servers = await self.server_repo.list_all()
        if not servers:
            raise KeyCreationError("no_servers")

        server = servers[0]

        try:
            key = await self.key_repo.create(
                user_id=user_id,
                server=server,
                auth_token=self.XRAY_AUTH_TOKEN,
                label=None,
            )
        except Exception as e:
            raise KeyCreationError(f"Failed to create key: {e}")

        await self.session.commit()
        await self.session.refresh(key)
        return True, key

    async def create_key_for_user(self, user_id: int, server_id: int, label: str | None = None):
        sub = await self.get_active_subscription(user_id)
        plan = sub.plan

        key_limit = int(getattr(plan, "key_limit", 0) or 0)

        active_keys = await self.list_active_keys(user_id)
        if key_limit and len(active_keys) >= key_limit:
            raise KeyCreationError(f"key limit reached {len(active_keys)}/{key_limit}")

        if any(getattr(k, "server_id", None) == server_id for k in active_keys):
            raise KeyCreationError("key on this server already exists")

        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise ServerNotFound("server not found")

        try:
            key = await self.key_repo.create(
                user_id=user_id,
                server=server,
                auth_token=self.XRAY_AUTH_TOKEN,
                label=label,
            )
        except Exception as e:
            raise KeyCreationError(f"Failed to create key on server {server_id}: {e}")

        await self.session.commit()
        await self.session.refresh(key)
        return key

    async def delete_key_for_user(self, user_id: int, key_id: int) -> bool:
        key = await self.key_repo.get_by_id(key_id, with_server=False)
        if not key or key.user_id != user_id:
            return False

        ok = await self.key_repo.delete(key_id, auth_token=self.XRAY_AUTH_TOKEN)
        await self.session.commit()
        return bool(ok)
