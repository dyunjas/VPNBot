from fastapi import APIRouter, Depends, Request
from backend.services.admin_security import check_origin, rate_limit


async def cabinet_security_guard(request: Request):
    path = request.url.path
    if path.startswith("/api/auth/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        await rate_limit(request, "cabinet-auth", maximum=30, window=60)
    elif request.method not in {"GET", "HEAD", "OPTIONS"}:
        # Shared IP budget applies before any expensive billing/identity operation.
        await rate_limit(request, "cabinet-write", maximum=60, window=60)

from api.cabinet.routes import (
    account_router,
    auth_router,
    billing_router,
    referral_router,
)

router = APIRouter(prefix="/api", tags=["cabinet"], dependencies=[Depends(cabinet_security_guard)])
router.include_router(auth_router)
router.include_router(account_router)
router.include_router(referral_router)
router.include_router(billing_router)
