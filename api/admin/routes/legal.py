from fastapi import APIRouter, Depends
from api.admin.common import require_superadmin_auth
from backend.services.legal_documents import (
    LEGAL_DOCUMENTS, LegalDocumentKey, LegalDocumentPayload,
    get_legal_document, update_legal_document,
)

router = APIRouter()


@router.get("/legal", dependencies=[Depends(require_superadmin_auth)])
async def admin_legal_list():
    return {"ok": True, "items": [{"key": key, "title": meta["title"], "url": "/terms/" if key == "terms" else f"/terms/{key}/"} for key, meta in LEGAL_DOCUMENTS.items()]}


@router.get("/legal/{key}", dependencies=[Depends(require_superadmin_auth)])
async def admin_legal_get(key: LegalDocumentKey):
    return await get_legal_document(key)


@router.put("/legal/{key}", dependencies=[Depends(require_superadmin_auth)])
async def admin_legal_update(key: LegalDocumentKey, payload: LegalDocumentPayload):
    return await update_legal_document(key, payload)
