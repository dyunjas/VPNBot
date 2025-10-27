import aiohttp
from server.core.loader import settings
from collections import OrderedDict

PALLY_API_URL_CREATE = "https://pal24.pro/api/v1/bill/create"
PALLY_API_URL_STATUS = "https://pal24.pro/api/v1/bill/status"

PALLY_SHOP_ID = settings.PALLY_SHOP_ID
PALLY_API_TOKEN = settings.PALLY_API_TOKEN

session: aiohttp.ClientSession | None = None


async def get_session() -> aiohttp.ClientSession:
    global session
    if session is None or session.closed:
        timeout = aiohttp.ClientTimeout(total=20)
        session = aiohttp.ClientSession(timeout=timeout)
    return session


async def create_invoice_PALLY(amount, order_id, description,
                               success_url=None, fail_url=None, ttl=600):
    data = OrderedDict([
        ("amount", round(float(amount), 2)),
        ("shop_id", PALLY_SHOP_ID),
        ("order_id", str(order_id)),
        ("description", description),
        ("type", "normal"),
        ("currency_in", "RUB"),
        ("name", "SHOPCHEK"),
        ("ttl", ttl)
    ])

    if success_url:
        data["success_url"] = success_url
    if fail_url:
        data["fail_url"] = fail_url

    headers = {
        "Authorization": f"Bearer {PALLY_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    session = await get_session()
    async with session.post(PALLY_API_URL_CREATE, json=data, headers=headers) as resp:
        return await resp.json()

async def get_invoice_status_PALLY(bill_id: str):
    headers = {
        "Authorization": f"Bearer {PALLY_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    session = await get_session()
    async with session.get(f"{PALLY_API_URL_STATUS}?id={bill_id}", headers=headers) as resp:
        return await resp.json()