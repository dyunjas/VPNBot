from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.admin.common import require_superadmin_auth
from backend.apps.common import LEGAL_DIR

router = APIRouter()

LegalDocumentKey = Literal["terms", "privacy", "offer"]

LEGAL_DOCUMENTS: dict[str, dict[str, str]] = {
    "terms": {"title": "Пользовательское соглашение", "filename": "terms.html"},
    "privacy": {"title": "Политика конфиденциальности", "filename": "privacy.html"},
    "offer": {"title": "Оферта", "filename": "offer.html"},
}


class LegalDocumentPayload(BaseModel):
    html: str = Field(min_length=1, max_length=250_000)


def _legal_path(key: str) -> Path:
    meta = LEGAL_DOCUMENTS.get(key)
    if not meta:
        raise HTTPException(status_code=404, detail="legal document not found")
    path = (LEGAL_DIR / meta["filename"]).resolve()
    if path.parent != LEGAL_DIR.resolve():
        raise HTTPException(status_code=400, detail="invalid legal document path")
    return path


@router.get("/legal", dependencies=[Depends(require_superadmin_auth)])
async def admin_legal_list():
    return {
        "ok": True,
        "items": [
            {
                "key": key,
                "title": meta["title"],
                "url": "/terms/" if key == "terms" else f"/terms/{key}/",
            }
            for key, meta in LEGAL_DOCUMENTS.items()
        ],
    }


@router.get("/legal/{key}", dependencies=[Depends(require_superadmin_auth)])
async def admin_legal_get(key: LegalDocumentKey):
    path = _legal_path(key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="legal document file not found")
    return {
        "ok": True,
        "key": key,
        "title": LEGAL_DOCUMENTS[key]["title"],
        "html": path.read_text(encoding="utf-8"),
        "url": "/terms/" if key == "terms" else f"/terms/{key}/",
    }


@router.put("/legal/{key}", dependencies=[Depends(require_superadmin_auth)])
async def admin_legal_update(key: LegalDocumentKey, payload: LegalDocumentPayload):
    path = _legal_path(key)
    html = payload.html.strip()
    if "<html" not in html.lower() or "</html>" not in html.lower():
        raise HTTPException(status_code=400, detail="document must be a full html page")
    path.write_text(html + "\n", encoding="utf-8")
    return {
        "ok": True,
        "key": key,
        "title": LEGAL_DOCUMENTS[key]["title"],
        "url": "/terms/" if key == "terms" else f"/terms/{key}/",
    }
