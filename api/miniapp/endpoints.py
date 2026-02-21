from fastapi import APIRouter
from api.miniapp.routes import (
    profile_router,
    subscriptions_router,
    billing_router,
    account_router,
)

router = APIRouter(prefix="/mini", tags=["mini-app"] )
router.include_router(profile_router)
router.include_router(subscriptions_router)
router.include_router(billing_router)
router.include_router(account_router)
