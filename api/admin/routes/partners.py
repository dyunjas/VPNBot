from sqlalchemy.exc import IntegrityError

from ..common import *

router = APIRouter()


@router.get("/partners", dependencies=[Depends(require_superadmin_auth)])
async def admin_partners(search: str | None = Query(default=None)):
    async with async_session() as session:
        service = PartnerService(session)
        items = await service.list_links_with_stats(search=search)

    return {
        "ok": True,
        "items": [
            {
                "id": item["id"],
                "name": item["name"],
                "code": item["code"],
                "url": item["url"],
                "is_active": item["is_active"],
                "new_users": item["new_users"],
                "paid_topups": item["paid_topups"],
                "paid_amount": item["paid_amount"],
                "created_at": _to_iso(item["created_at"]),
            }
            for item in items
        ],
    }


@router.post("/partners", dependencies=[Depends(require_superadmin_auth)])
async def admin_partner_create(payload: PartnerLinkCreatePayload):
    async with async_session() as session:
        service = PartnerService(session)
        try:
            link = await service.create_link(name=payload.name, code=payload.code)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Партнерский код уже существует")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {
        "ok": True,
        "item": {
            "id": link.id,
            "name": link.name,
            "code": link.code,
            "url": PartnerService.build_url(link.code),
            "is_active": bool(link.is_active),
            "created_at": _to_iso(link.created_at),
        },
    }


@router.patch("/partners/{link_id}", dependencies=[Depends(require_superadmin_auth)])
async def admin_partner_update(link_id: int, payload: PartnerLinkUpdatePayload):
    async with async_session() as session:
        service = PartnerService(session)
        updated = await service.set_active(link_id=link_id, is_active=payload.is_active)
        if updated <= 0:
            raise HTTPException(status_code=404, detail="Партнерская ссылка не найдена")

    return {"ok": True}


@router.get("/partners/{link_id}/details", dependencies=[Depends(require_superadmin_auth)])
async def admin_partner_details(link_id: int):
    async with async_session() as session:
        service = PartnerService(session)
        details = await service.get_link_details(link_id=link_id)
        if not details:
            raise HTTPException(status_code=404, detail="Партнерская ссылка не найдена")

    return {
        "ok": True,
        "link": {
            **details["link"],
            "created_at": _to_iso(details["link"]["created_at"]),
        },
        "summary": {
            **details["summary"],
            "last_payment_at": _to_iso(details["summary"]["last_payment_at"]),
        },
        "users": [
            {
                **item,
                "user_created_at": _to_iso(item["user_created_at"]),
                "attributed_at": _to_iso(item["attributed_at"]),
                "last_paid_at": _to_iso(item["last_paid_at"]),
            }
            for item in details["users"]
        ],
        "recent_payments": [
            {
                **item,
                "paid_at": _to_iso(item["paid_at"]),
                "attributed_at": _to_iso(item["attributed_at"]),
            }
            for item in details["recent_payments"]
        ],
    }
