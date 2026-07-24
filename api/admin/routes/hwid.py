from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database.models import UserDevice
from backend.database.session import async_session
from backend.services.exceptions import DeviceNotFound, UserNotFound
from backend.services.hwid_service import HwidService
from ..common import require_superadmin_auth


# DTOs
class HwidDeviceResponse(BaseModel):
    hwid: str
    userUuid: str
    platform: Optional[str] = None
    osVersion: Optional[str] = None
    deviceModel: Optional[str] = None
    userAgent: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, device: UserDevice, user_uuid: str) -> HwidDeviceResponse:
        return cls(
            hwid=device.hwid,
            userUuid=user_uuid,
            platform=device.device_os,
            osVersion=device.os_version,
            deviceModel=device.device_model,
            userAgent=device.user_agent,
            createdAt=device.first_seen_at,
            updatedAt=device.last_seen_at,
        )


class CreateUserHwidDeviceRequestDto(BaseModel):
    hwid: str
    userUuid: str = Field(..., alias="userUuid")
    platform: Optional[str] = None
    osVersion: Optional[str] = None
    deviceModel: Optional[str] = None
    userAgent: Optional[str] = None


class DeleteUserHwidDeviceRequestDto(BaseModel):
    userUuid: str = Field(..., alias="userUuid")
    hwid: str


class DeleteAllUserHwidDevicesRequestDto(BaseModel):
    userUuid: str = Field(..., alias="userUuid")


class GetAllHwidDevicesResponse(BaseModel):
    response: dict


class GetUserHwidDevicesResponse(BaseModel):
    response: dict


class HwidStatsResponse(BaseModel):
    response: dict


class TopUsersResponse(BaseModel):
    response: dict


router = APIRouter(prefix="/api/hwid", tags=["hwid"])


@router.get("/devices", dependencies=[Depends(require_superadmin_auth)])
async def get_all_devices(
    size: int = Query(10, ge=1, le=100),
    start: int = Query(0, ge=0),
):
    async with async_session() as session:
        service = HwidService(session)
        try:
            devices, total = await service.get_all_devices(size=size, start=start)

            devices_response = []
            for device in devices:
                user = await service.get_user_by_uuid(device.user.remnawave_user_uuid)
                devices_response.append(HwidDeviceResponse.from_model(device, user.remnawave_user_uuid))

            return {
                "response": {
                    "devices": [d.model_dump(by_alias=True) for d in devices_response],
                    "total": total,
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices", dependencies=[Depends(require_superadmin_auth)])
async def create_device(data: CreateUserHwidDeviceRequestDto):
    async with async_session() as session:
        service = HwidService(session)
        try:
            device = await service.create_device(
                hwid=data.hwid,
                user_uuid=data.userUuid,
                platform=data.platform,
                os_version=data.osVersion,
                device_model=data.deviceModel,
                user_agent=data.userAgent,
            )

            user = await service.get_user_by_uuid(data.userUuid)
            device_response = HwidDeviceResponse.from_model(device, user.remnawave_user_uuid)

            return {
                "response": {
                    "total": 1,
                    "devices": [device_response.model_dump(by_alias=True)],
                }
            }
        except UserNotFound:
            raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/delete", dependencies=[Depends(require_superadmin_auth)])
async def delete_device(data: DeleteUserHwidDeviceRequestDto):
    async with async_session() as session:
        service = HwidService(session)
        try:
            device = await service.delete_device(user_uuid=data.userUuid, hwid=data.hwid)

            user = await service.get_user_by_uuid(data.userUuid)
            device_response = HwidDeviceResponse.from_model(device, user.remnawave_user_uuid)

            return {
                "response": {
                    "total": 1,
                    "devices": [device_response.model_dump(by_alias=True)],
                }
            }
        except UserNotFound:
            raise HTTPException(status_code=404, detail="User not found")
        except DeviceNotFound:
            raise HTTPException(status_code=404, detail="Device not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/delete-all", dependencies=[Depends(require_superadmin_auth)])
async def delete_all_devices(data: DeleteAllUserHwidDevicesRequestDto):
    async with async_session() as session:
        service = HwidService(session)
        try:
            devices = await service.delete_all_devices(user_uuid=data.userUuid)

            user = await service.get_user_by_uuid(data.userUuid)
            devices_response = [HwidDeviceResponse.from_model(d, user.remnawave_user_uuid) for d in devices]

            return {
                "response": {
                    "total": len(devices),
                    "devices": [d.model_dump(by_alias=True) for d in devices_response],
                }
            }
        except UserNotFound:
            raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/stats", dependencies=[Depends(require_superadmin_auth)])
async def get_stats():
    async with async_session() as session:
        service = HwidService(session)
        try:
            stats = await service.get_stats()
            return {"response": stats}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/top-users", dependencies=[Depends(require_superadmin_auth)])
async def get_top_users(
    size: int = Query(10, ge=1, le=100),
    start: int = Query(0, ge=0),
):
    async with async_session() as session:
        service = HwidService(session)
        try:
            users, total = await service.get_top_users(size=size, start=start)
            return {
                "response": {
                    "users": users,
                    "total": total,
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{userUuid}", dependencies=[Depends(require_superadmin_auth)])
async def get_user_devices(userUuid: str):
    async with async_session() as session:
        service = HwidService(session)
        try:
            devices = await service.get_user_devices(user_uuid=userUuid)
            devices_response = [HwidDeviceResponse.from_model(d, userUuid) for d in devices]

            return {
                "response": {
                    "total": len(devices),
                    "devices": [d.model_dump(by_alias=True) for d in devices_response],
                }
            }
        except UserNotFound:
            raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
