import aiohttp
from datetime import datetime
from urllib.parse import urlparse
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from server.database.models import Key, KeyStatus, Server

from server.core.logger_config import logger


class KeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _count_active_keys(self, user_id: int) -> int:
        q = select(func.count()).select_from(Key).where(
            Key.user_id == user_id,
            Key.status == KeyStatus.active
        )
        res = await self.session.execute(q)
        return int(res.scalar() or 0)

    def _normalize_agent_base(self, grpc_endpoint: str) -> str:

        if not grpc_endpoint:
            raise Exception("У сервера не задан grpc_endpoint")
        parsed = urlparse(grpc_endpoint)
        if not parsed.scheme:
            return f"http://{grpc_endpoint}"
        return grpc_endpoint

    async def create_key(
        self,
        user_id: int,
        server: Server,
        auth_token: str,
        *,
        max_keys_per_user: int = 2,
        label: str | None = None,
    ) -> Key:

        active = await self._count_active_keys(user_id)
        if active >= max_keys_per_user:
            raise Exception(f"У пользователя уже {active} активных ключ(а), лимит = {max_keys_per_user}")

        agent_base = self._normalize_agent_base(server.grpc_endpoint)

        email = f"user-{user_id}@lunet"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        payload = {"email": email}

        async with aiohttp.ClientSession() as http:
            async with http.post(f"{agent_base}/add_user", json=payload, headers=headers) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    raise Exception(f"xray-agent add_user HTTP {resp.status}: {text}")

        if not data.get("ok"):
            raise Exception(f"Ошибка создания ключа на {server.public_host}: {data}")

        user_uuid = data["uuid"]

        params = [
            "encryption=none",
            "type=tcp",
            "security=reality",
            f"pbk={server.pbk}",
            f"sni={server.sni}",
            f"fp={server.fp}",
        ]
        if server.short_id:
            params.append(f"sid={server.short_id}")

        label = server.country
        uri = f"vless://{user_uuid}@{server.public_host}:{server.port}?{'&'.join(params)}#LunetVPN | {label}"

        key = Key(
            user_id=user_id,
            server_id=server.id,
            uuid=user_uuid,
            uri=uri,
            status=KeyStatus.active,
            created_at=datetime.now(),
        )

        self.session.add(key)
        await self.session.commit()
        await self.session.refresh(key)
        return key

    async def delete_key(
        self,
        key_id: int,
        auth_token: str,
    ) -> bool:
        res = await self.session.execute(select(Key).where(Key.id == key_id))
        key = res.scalar_one_or_none()
        if not key:
            return False

        server = await self.session.get(Server, key.server_id)
        if not server:
            await self.session.execute(delete(Key).where(Key.id == key_id))
            await self.session.commit()
            return True

        agent_base = self._normalize_agent_base(server.grpc_endpoint)
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        payload = {"email": f"user-{key.user_id}@lunet"}

        async with aiohttp.ClientSession() as http:
            async with http.post(f"{agent_base}/remove_user", json=payload, headers=headers) as resp:
                try:
                    _ = await resp.json()
                except Exception:
                    _ = await resp.text()

        await self.session.execute(delete(Key).where(Key.id == key_id))
        await self.session.commit()
        return True

    async def get_keys_by_user_id(self, user_id: int) -> list[Key]:
        q = (
            select(Key)
            .where(Key.user_id == user_id)
            .options(selectinload(Key.server))
        )
        result = await self.session.execute(q)
        return result.scalars().all()

    async def get_all_active_keys(self) -> list[Key]:
        res = await self.session.execute(
            select(Key).where(Key.status == KeyStatus.active)
        )
        return res.scalars().all()

    async def deactivate_expired_keys(self) -> int:
        now = datetime.now()
        res = await self.session.execute(
            select(Key).where(Key.status == KeyStatus.active, Key.expires_at < now)
        )
        keys = res.scalars().all()
        for k in keys:
            k.status = KeyStatus.deleted
        await self.session.commit()
        return len(keys) 

    async def get_key_by_id(self, key_id: int) -> Key | None:
        q = (
            select(Key)
            .where(Key.id == key_id)
            .options(selectinload(Key.server))
        )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()
    
    async def delete_all_keys_for_user(self, user_id: int, auth_token: str) -> int:
        q = (
            select(Key)
            .where(Key.user_id == user_id, Key.status == KeyStatus.active)
            .options(selectinload(Key.server))
        )
        result = await self.session.execute(q)
        keys: list[Key] = result.scalars().all()

        deleted = 0
        for key in keys:
            try:
                ok = await self.delete_key(key.id, auth_token=auth_token)
                if ok:
                    deleted += 1
            except Exception as e:
                logger.error(f"[revoke_keys_for_user] failed key_id={key.id}: {e}")

        return deleted
    
    async def get_user_key_on_server(self, user_id: int, server_id: int, statuses: list[KeyStatus]):
        return await self.session.scalar(
            select(Key).where(
                Key.user_id == user_id,
                Key.server_id == server_id,
                Key.status.in_(statuses)
            ).limit(1)
        )