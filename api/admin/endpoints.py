from fastapi import APIRouter

from api.admin.routes import (
    auth_router,
    broadcast_router,
    plans_router,
    referrals_router,
    subscriptions_router,
    transactions_router,
    users_router,
    withdrawals_router,
    logs_router,
    partners_router,
    promocodes_router,
    system_router,
)

router = APIRouter(prefix="/api/admin", tags=["admin-web"])
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(subscriptions_router)
router.include_router(plans_router)
router.include_router(transactions_router)
router.include_router(broadcast_router)
router.include_router(withdrawals_router)
router.include_router(referrals_router)
router.include_router(logs_router)
router.include_router(promocodes_router)
router.include_router(partners_router)
router.include_router(system_router)
