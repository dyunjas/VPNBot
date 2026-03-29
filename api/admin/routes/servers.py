from fastapi import APIRouter
from sqlalchemy.exc import IntegrityError
from ..common import *

router = APIRouter()

@router.get("/servers", dependencies=[Depends(require_admin_auth)])
async def admin_servers():
    async with async_session() as session:
        repo = ServerRepository(session)
        rows = await repo.list_with_load()
    return {
        "ok": True,
        "items": [
            {
                "id": server.id,
                "country": server.country,
                "public_host": server.public_host,
                "grpc_endpoint": server.grpc_endpoint,
                "port": server.port,
                "active_keys_count": active_cnt,
                "total_keys_count": total_cnt,
                "created_at": _to_iso(server.created_at),
            }
            for server, active_cnt, total_cnt in rows
        ],
    }

@router.post("/servers", dependencies=[Depends(require_admin_auth)])
async def admin_server_create(payload: ServerCreatePayload):
    async with async_session() as session:
        server = Server(
            country=payload.country.strip(),
            inbound_tag=payload.inbound_tag.strip(),
            grpc_endpoint=payload.grpc_endpoint.strip(),
            public_host=payload.public_host.strip(),
            port=payload.port,
            sni=payload.sni.strip(),
            fp=payload.fp.strip(),
            pbk=payload.pbk.strip(),
            short_id=(payload.short_id or None),
            note=(payload.note or None),
            created_at=datetime.now(timezone.utc),
        )
        session.add(server)
        await session.commit()
        await session.refresh(server)
        return {"ok": True, "server_id": server.id}


@router.post("/servers/{server_id}/action", dependencies=[Depends(require_admin_auth)])
async def admin_server_action(server_id: int, payload: ServerActionPayload):
    async with async_session() as session:
        admin_service = AdminService(session)
        try:
            if payload.action == "health":
                data = await admin_service.get_server_health(server_id)
            elif payload.action == "stats":
                data = await admin_service.get_server_stats(server_id)
            else:
                data = await admin_service.resync_server(server_id)
            return {"ok": True, "action": payload.action, "result": data}
        except ServerNotFound as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.delete("/servers/{server_id}", dependencies=[Depends(require_admin_auth)])
async def admin_server_delete(server_id: int):
    async with async_session() as session:
        server = _http_404_if_none(await session.get(Server, server_id), "server not found")
        await session.delete(server)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=400,
                detail="cannot delete server with linked entities",
            )
        return {"ok": True}


