from __future__ import annotations

from ..common import *
from backend.core.maintenance import (
    MAINTENANCE_MESSAGE,
    disable_maintenance,
    enable_manual_maintenance,
    get_maintenance_state,
)

router = APIRouter()


class MaintenanceUpdatePayload(BaseModel):
    enabled: bool
    message: str | None = None


@router.get("/system/maintenance", dependencies=[Depends(require_admin_auth)])
async def admin_system_maintenance_state():
    state = get_maintenance_state()
    return {"ok": True, "maintenance": state}


@router.post("/system/maintenance", dependencies=[Depends(require_admin_auth)])
async def admin_system_maintenance_update(payload: MaintenanceUpdatePayload):
    if payload.enabled:
        state = enable_manual_maintenance(message=(payload.message or MAINTENANCE_MESSAGE), source="admin")
    else:
        state = disable_maintenance(source="admin")
    return {"ok": True, "maintenance": state}
