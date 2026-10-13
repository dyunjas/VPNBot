from fastapi import APIRouter, Depends, Request
from api.admin.common import require_admin_auth


async def admin_route_guard(request: Request):
    if request.url.path not in {"/api/admin/auth/login", "/api/admin/auth/verify-2fa"}:
        await require_admin_auth(request, authorization=None, x_admin_token=None, admin_access_token=None)

from api.admin.routes import (
    admins_router,
    auth_router,
    broadcast_router,
    plans_router,
    referrals_router,
    subscriptions_router,
    transactions_router,
    users_router,
    withdrawals_router,
    logs_router,
    legal_router,
    partners_router,
    promocodes_router,
    system_router,
    diagnostics_router,
    exports_router,
    servers_router,
)

router = APIRouter(prefix="/api/admin", tags=["admin-web"], dependencies=[Depends(admin_route_guard)])
router.include_router(auth_router)
router.include_router(admins_router)
router.include_router(users_router)
router.include_router(subscriptions_router)
router.include_router(plans_router)
router.include_router(transactions_router)
router.include_router(broadcast_router)
router.include_router(withdrawals_router)
router.include_router(referrals_router)
router.include_router(logs_router)
router.include_router(legal_router)
router.include_router(promocodes_router)
router.include_router(partners_router)
router.include_router(system_router)
router.include_router(diagnostics_router)
router.include_router(exports_router)
router.include_router(servers_router)
