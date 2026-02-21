from fastapi import APIRouter

from api.admin.routes import (
    auth_router,
    broadcast_router,
    plans_router,
    referrals_router,
    servers_router,
    subscriptions_router,
    transactions_router,
    users_router,
    withdrawals_router,
)

router = APIRouter(prefix="/admin-api", tags=["admin-web"])
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(subscriptions_router)
router.include_router(plans_router)
router.include_router(transactions_router)
router.include_router(servers_router)
router.include_router(broadcast_router)
router.include_router(withdrawals_router)
router.include_router(referrals_router)

