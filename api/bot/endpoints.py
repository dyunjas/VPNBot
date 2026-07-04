from fastapi import APIRouter

from api.bot.routes import (
    billing_router,
    profile_router,
    subscription_router,
    users_router,
)

router = APIRouter(prefix="/api", tags=["bot"])
router.include_router(users_router)
router.include_router(profile_router)
router.include_router(subscription_router)
router.include_router(billing_router)
