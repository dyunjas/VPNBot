from fastapi import APIRouter
from ..common import *

router = APIRouter()


@router.get("/promocodes", dependencies=[Depends(require_admin_auth)])
async def admin_promocodes():
    async with async_session() as session:
        promos = list(
            (await session.execute(select(Promocode).order_by(Promocode.created_at.desc(), Promocode.id.desc())))
            .scalars()
            .all()
        )
        used_counts = {
            int(pid): int(cnt)
            for pid, cnt in (
                await session.execute(
                    select(PromocodeActivation.promocode_id, func.count(PromocodeActivation.id))
                    .group_by(PromocodeActivation.promocode_id)
                )
            ).all()
        }

    return {
        "ok": True,
        "items": [
            {
                "id": p.id,
                "code": p.code,
                "amount": int(p.amount or 0),
                "usages_left": int(p.usages or 0),
                "used_count": used_counts.get(p.id, 0),
                "is_activated": bool(p.is_activated),
                "activated_at": _to_iso(p.activated_at),
                "created_at": _to_iso(p.created_at),
            }
            for p in promos
        ],
    }


@router.post("/promocodes", dependencies=[Depends(require_admin_auth)])
async def admin_promocode_create(payload: PromocodeCreatePayload):
    code = payload.code.strip()
    async with async_session() as session:
        exists = await session.scalar(select(Promocode.id).where(Promocode.code == code))
        if exists:
            raise HTTPException(status_code=400, detail="promocode with this code already exists")

        promo = Promocode(
            code=code,
            amount=payload.amount,
            usages=payload.usages,
            created_at=datetime.now(timezone.utc),
        )
        session.add(promo)
        await session.commit()
        await session.refresh(promo)
    return {"ok": True, "promocode_id": promo.id}


@router.delete("/promocodes/{promocode_id}", dependencies=[Depends(require_admin_auth)])
async def admin_promocode_delete(promocode_id: int):
    async with async_session() as session:
        promo = _http_404_if_none(await session.get(Promocode, promocode_id), "promocode not found")
        await session.delete(promo)
        await session.commit()
    return {"ok": True}
