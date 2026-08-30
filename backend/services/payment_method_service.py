from typing import Any

from backend.core.config import settings


PAYMENT_METHODS = ("cryptobot", "pally", "platega")


async def is_payment_method_enabled(session: Any, method: str) -> bool:
    # Payment methods are configured through environment settings only.
    return True


async def get_payment_method_config(session: Any, method: str) -> dict[str, Any]:
    if method == "cryptobot":
        return {"api_token": settings.CRYPTOBOT_SECRET}
    if method == "pally":
        return {"api_token": settings.PALLY_API_TOKEN, "shop_id": settings.PALLY_SHOP_ID,
                "success_url": settings.PALLY_SUCCESS_URL, "fail_url": settings.PALLY_FAIL_URL}
    if method == "platega":
        return {"merchant_id": settings.PLATEGA_MERCHANT_ID, "secret": settings.PLATEGA_SECRET,
                "method_card": settings.PLATEGA_METHOD_CARD, "method_sbp": settings.PLATEGA_METHOD_SBP}
    raise ValueError(f"unknown payment method: {method}")
