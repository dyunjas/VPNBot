from __future__ import annotations

from aiogram import Bot
from aiogram.types import LabeledPrice

from ..common import *
from backend.core.loader import bot as runtime_bot
from backend.core.logger_config import logger
from backend.core.business_config import list_business_settings, update_business_settings
from backend.core.maintenance import (
    MAINTENANCE_MESSAGE,
    disable_maintenance,
    enable_manual_maintenance,
    get_maintenance_state,
)
from backend.core.telegram import create_telegram_session

router = APIRouter()


class MaintenanceUpdatePayload(BaseModel):
    enabled: bool
    message: str | None = None


class StarsInvoicePayload(BaseModel):
    amount: int = Field(gt=0, le=100000)


class BusinessSettingsPayload(BaseModel):
    values: dict[str, str | int | float]


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


@router.post("/system/stars-invoice", dependencies=[Depends(require_admin_auth)])
async def admin_system_stars_invoice(payload: StarsInvoicePayload):
    amount = int(payload.amount or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    bot_instance = runtime_bot
    temp_bot: Bot | None = None
    if bot_instance is None:
        bot_token = (settings.BOT_TOKEN or "").strip()
        if not bot_token:
            raise HTTPException(status_code=503, detail="BOT_TOKEN is not configured")
        temp_bot = Bot(token=bot_token, session=create_telegram_session())
        bot_instance = temp_bot

    invoice_payload = f"admin_stars_topup:{uuid.uuid4().hex}:{amount}"
    try:
        invoice_url = await bot_instance.create_invoice_link(
            title="Пополнение баланса бота",
            description=f"Пополнение баланса Telegram Stars бота на {amount} ⭐",
            payload=invoice_payload,
            currency="XTR",
            prices=[LabeledPrice(label="Telegram Stars", amount=amount)],
            provider_token="",
        )
    except Exception as exc:
        logger.exception("[admin][system] stars invoice creation failed amount=%s", amount)
        raise HTTPException(status_code=502, detail=f"failed to create Stars invoice: {exc}")
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()

    return {
        "ok": True,
        "amount": amount,
        "currency": "XTR",
        "invoice_url": invoice_url,
        "payload": invoice_payload,
    }


@router.get("/system/business-settings", dependencies=[Depends(require_admin_auth)])
async def admin_system_business_settings():
    return {"ok": True, "items": list_business_settings()}


@router.put("/system/business-settings", dependencies=[Depends(require_admin_auth)])
async def admin_system_business_settings_update(payload: BusinessSettingsPayload):
    try:
        items = update_business_settings(payload.values)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"unknown setting: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "items": items}
