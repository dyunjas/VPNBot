from fastapi import APIRouter

from api.cabinet.routes import (
    account_router,
    auth_router,
    billing_router,
    referral_router,
)

router = APIRouter(prefix="/api", tags=["cabinet"])
router.include_router(auth_router)
router.include_router(account_router)
router.include_router(referral_router)
router.include_router(billing_router)
