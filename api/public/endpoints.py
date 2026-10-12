from fastapi import APIRouter, Response

from backend.core.business_config import get_business_decimal, get_business_int
from backend.database.session import async_session
from backend.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/catalog")
async def public_catalog(response: Response):
    response.headers["Cache-Control"] = "no-store"
    async with async_session() as session:
        plans = await SubscriptionService(session).list_plans()
        return {
            "plans": [{
                "id": plan.id, "name": plan.name, "price": str(plan.price),
                "period_days": plan.period_days,
                "gb_limit": int(plan.gb_limit or 0),
                "device_limit": int(plan.device_limit or 0),
            } for plan in plans],
            "traffic_price_per_gb": str(get_business_decimal("TRAFFIC_PRICE_PER_GB_RUB")),
            "min_traffic_purchase_gb": get_business_int("MIN_TRAFFIC_PURCHASE_GB"),
        }

