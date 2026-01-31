import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.database.session import async_session

from backend.services import UserService, SubscriptionService, VPNService
from backend.services.exceptions import UserNotFound, SubscriptionNotFound

from api.subscription_url.utils import (
    _build_expire_only_header,
    _profile_title,
    _profile_update_interval,
    _profile_web_page,
    expired_subscription_response,
)

router = APIRouter(tags=["subscription"])

XRAY_AUTH_TOKEN = settings.XRAY_AUTH


AsyncSessionGenerator = AsyncGenerator[AsyncSession, None]


async def get_session() -> AsyncSessionGenerator:
    async with async_session() as session:
        yield session

def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


def get_subscription_service(session: AsyncSession = Depends(get_session)) -> SubscriptionService:
    return SubscriptionService(session)


def get_vpn_service(session: AsyncSession = Depends(get_session)) -> VPNService:
    return VPNService(session=session, xray_auth_token=XRAY_AUTH_TOKEN)


@router.get("/sub/{token}", response_model=None)
async def subscription(
    token: str,
    user_service: UserService = Depends(get_user_service),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    vpn_service: VPNService = Depends(get_vpn_service),
):
    try:
        user = await user_service.get_by_subscription_token(token)
    except UserNotFound:
        logger.warning(f"[subscription] token not found: {token}")
        headers: dict[str, str] = {}
        headers |= _profile_title("🌙 Lunet VPN")
        headers |= _profile_update_interval(6)
        headers |= _profile_web_page("https://t.me/LunetVpnBot")
        return expired_subscription_response(headers=headers)

    headers: dict[str, str] = {}
    headers |= _profile_title("🌙 Lunet VPN")
    headers |= _profile_update_interval(6)
    headers |= _profile_web_page("https://t.me/LunetVpnBot")

    try:
        subscription_obj = await subscription_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        return expired_subscription_response(headers=headers)

    # ✅ всегда сравниваем в UTC (и не падаем если None)
    now = datetime.now(timezone.utc)

    if not subscription_obj.current_period_end:
        return expired_subscription_response(headers=headers)

    # current_period_end может быть naive -> приводим к UTC аккуратно
    end_dt = subscription_obj.current_period_end
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    headers |= _build_expire_only_header(end_dt)

    if end_dt <= now:
        return expired_subscription_response(headers=headers)

    plan = subscription_obj.plan
    if not plan:
        logger.error(f"[subscription] plan not loaded user_id={user.id}")
        return expired_subscription_response(headers=headers)

    try:
        keys_by_server = await vpn_service.get_or_create_keys(user_id=user.id)
    except Exception as e:
        logger.error(f"[subscription] get_or_create_keys failed user_id={user.id}: {e}")
        return expired_subscription_response(headers=headers)

    uris = list(keys_by_server.values())
    if not uris:
        return expired_subscription_response(headers=headers)

    plain = "\n".join(uris).strip()
    b64 = base64.b64encode(plain.encode("utf-8")).decode("ascii")

    return Response(
        content=b64,
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )
