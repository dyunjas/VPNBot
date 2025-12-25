import base64
from datetime import datetime, timezone
from fastapi import APIRouter, Response
from sqlalchemy import select

from server.database.session import async_session
from server.database.models import User, KeyStatus

from server.repositories.key_repository import KeyRepository
from server.repositories.server_repository import ServerRepository
from server.repositories.subscription_repository import SubscriptionRepository

from server.core.loader import settings
from server.core.logger_config import logger

from api.subscription_url.utils import (
    _build_expire_only_header,
    _profile_title,
    _profile_update_interval,
    _profile_web_page,
    expired_subscription_response
)

router = APIRouter(tags=["subscription"])

XRAY_AUTH_TOKEN = settings.XRAY_AUTH


@router.get("/sub/{token}")
async def subscription(token: str):
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.subscription_token == token)
        )

        headers: dict[str, str] = {}
        headers |= _profile_title("🌙 Lunet VPN")
        headers |= _profile_update_interval(6)
        headers |= _profile_web_page("https://t.me/LunetVpnBot")

        if not user:
            logger.warning(f"[subscription] token not found: {token}")
            return expired_subscription_response(headers=headers)

        sub_repo = SubscriptionRepository(session)
        subscription_obj = await sub_repo.get_user_subscription_by_tg_id(user.tg_id)

        if subscription_obj and subscription_obj.current_period_end:
            headers |= _build_expire_only_header(
                subscription_obj.current_period_end
            )

        if (
            not subscription_obj
            or not subscription_obj.current_period_end
            or subscription_obj.current_period_end <= datetime.now()
        ):
            return expired_subscription_response(headers=headers)

        plan = subscription_obj.plan
        if not plan:
            logger.error(f"[subscription] plan not loaded user_id={user.id}")
            return expired_subscription_response(headers=headers)

        key_repo = KeyRepository(session)
        server_repo = ServerRepository(session)

        servers = await server_repo.get_all_servers()

        existing_keys = await key_repo.get_keys_by_user_id(user.id)
        active_keys = [k for k in existing_keys if k.status == KeyStatus.active]

        keys_by_server: dict[int, str] = {
            k.server_id: k.uri
            for k in active_keys
            if k.server_id and k.uri
        }

        limit = int(getattr(plan, "key_limit", 0) or 0)

        for server in servers:
            if server.id in keys_by_server:
                continue

            if limit and len(keys_by_server) >= limit:
                break

            try:
                key = await key_repo.create_key(
                    user_id=user.id,
                    server=server,
                    auth_token=XRAY_AUTH_TOKEN
                )
                keys_by_server[server.id] = key.uri
            except Exception as e:
                logger.error(
                    f"[subscription] create_key failed user_id={user.id} server_id={server.id}: {e}"
                )

        uris = [keys_by_server[s.id] for s in servers if s.id in keys_by_server]

    if not uris:
        return expired_subscription_response(headers=headers)

    plain = "\n".join(uris).strip()
    b64 = base64.b64encode(plain.encode("utf-8")).decode("ascii")

    return Response(
        content=b64,
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )
