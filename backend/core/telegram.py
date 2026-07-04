from aiogram.client.session.aiohttp import AiohttpSession

from backend.core.config import settings


def create_telegram_session() -> AiohttpSession:
    proxy_url = settings.TELEGRAM_PROXY_URL
    if proxy_url:
        return AiohttpSession(proxy=proxy_url)
    return AiohttpSession()
