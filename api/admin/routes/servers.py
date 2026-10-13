from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from api.admin.common import require_superadmin_auth
from backend.services.remnawave_nodes import RemnawaveNodesService

router=APIRouter()


class NodeActionPayload(BaseModel):
    action: Literal["enable","disable","restart","force_restart","reset_traffic","delete"]


class NodeConfigProfile(BaseModel):
    activeConfigProfileUuid: UUID
    activeInbounds: list[UUID] = Field(max_length=100)


class NodeUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None,min_length=3,max_length=30)
    address: str | None = Field(default=None,min_length=2,max_length=253,pattern=r"^[A-Za-z0-9.\-:\[\]]+$")
    port: int | None = Field(default=None,ge=1,le=65535)
    countryCode: str | None = Field(default=None,pattern=r"^[A-Z]{2}$")
    note: str | None = Field(default=None,max_length=255)
    tags: list[Annotated[str, Field(min_length=1,max_length=36,pattern=r"^[A-Z0-9_:]+$")]] | None = Field(default=None,max_length=10)
    isTrafficTrackingActive: bool | None = None
    trafficLimitBytes: int | None = Field(default=None,ge=0)
    trafficResetDay: int | None = Field(default=None,ge=1,le=31)
    notifyPercent: int | None = Field(default=None,ge=0,le=100)
    consumptionMultiplier: float | None = Field(default=None,ge=0,le=100,allow_inf_nan=False)
    configProfile: NodeConfigProfile | None = None


class BulkActionPayload(BaseModel):
    uuids: list[UUID] = Field(min_length=1,max_length=100)
    action: Literal["enable","disable","restart","reset_traffic"]


class RestartAllPayload(BaseModel):
    forceRestart: bool = False


@router.get("/servers",dependencies=[Depends(require_superadmin_auth)])
async def admin_servers():
    return await RemnawaveNodesService().list_nodes()


@router.get("/servers/config-profiles",dependencies=[Depends(require_superadmin_auth)])
async def admin_server_profiles():
    return await RemnawaveNodesService().profiles()


@router.get("/servers/config-profiles/{profile_uuid}/inbounds",dependencies=[Depends(require_superadmin_auth)])
async def admin_server_inbounds(profile_uuid: UUID):
    return await RemnawaveNodesService().inbounds(profile_uuid)


@router.patch("/servers/{node_uuid}",dependencies=[Depends(require_superadmin_auth)])
async def admin_server_update(node_uuid: UUID,payload: NodeUpdatePayload):
    if not payload.model_dump(exclude_none=True):
        from fastapi import HTTPException
        raise HTTPException(400,"Укажите изменения настроек сервера")
    return await RemnawaveNodesService().save_node(payload.model_dump(mode="json",exclude_none=True),node_uuid)


@router.post("/servers/actions/bulk",dependencies=[Depends(require_superadmin_auth)])
async def admin_servers_bulk(payload: BulkActionPayload):
    return await RemnawaveNodesService().bulk_action(payload.uuids,payload.action)


@router.post("/servers/actions/restart-all",dependencies=[Depends(require_superadmin_auth)])
async def admin_servers_restart_all(payload: RestartAllPayload):
    return await RemnawaveNodesService().restart_all(payload.forceRestart)


@router.post("/servers/{node_uuid}/action",dependencies=[Depends(require_superadmin_auth)])
async def admin_server_action(node_uuid: UUID,payload: NodeActionPayload):
    return await RemnawaveNodesService().action(node_uuid,payload.action)
