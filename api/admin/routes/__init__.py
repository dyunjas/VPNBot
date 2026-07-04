from .auth import router as auth_router
from .users import router as users_router
from .subscriptions import router as subscriptions_router
from .plans import router as plans_router
from .transactions import router as transactions_router
from .broadcast import router as broadcast_router
from .withdrawals import router as withdrawals_router
from .referrals import router as referrals_router
from .logs import router as logs_router
from .promocodes import router as promocodes_router
from .partners import router as partners_router
from .system import router as system_router

__all__ = [
    "auth_router",
    "users_router",
    "subscriptions_router",
    "plans_router",
    "transactions_router",
    "broadcast_router",
    "withdrawals_router",
    "referrals_router",
    "logs_router",
    "promocodes_router",
    "partners_router",
    "system_router",
]
