from __future__ import annotations

import re
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


_LEGAL_CARD_RE = re.compile(
    r"(<main\b[^>]*>\s*<section\b[^>]*class=[\"'][^\"']*\bcard\b[^\"']*[\"'][^>]*>)(.*?)(</section>\s*</main>)",
    re.IGNORECASE | re.DOTALL,
)
_LEGAL_MAIN_RE = re.compile(r"(<main\b[^>]*>)(.*?)(</main>)", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_CONTENT_RE = re.compile(
    r"<\s*/?\s*(?:html|head|body|script|style|iframe|object|embed|form|input|button|textarea|select|option|link|meta|base|img|svg)\b",
    re.IGNORECASE,
)
_FORBIDDEN_ATTR_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
_FORBIDDEN_URL_RE = re.compile(r"\s(?:href|src)\s*=\s*([\"'])\s*javascript:", re.IGNORECASE)


def _extract_legal_content(page_html: str) -> str:
    match = _LEGAL_CARD_RE.search(page_html)
    if match:
        return match.group(2).strip()
    match = _LEGAL_MAIN_RE.search(page_html)
    if match:
        return match.group(2).strip()
    return page_html.strip()


def _validate_legal_content(content: str) -> str:
    html = content.strip()
    if _FORBIDDEN_CONTENT_RE.search(html):
        raise HTTPException(status_code=400, detail="edit only document text, not full html page")
    if _FORBIDDEN_ATTR_RE.search(html) or _FORBIDDEN_URL_RE.search(html):
        raise HTTPException(status_code=400, detail="unsafe html attributes are not allowed")
    return html


def _replace_legal_content(page_html: str, content: str) -> str:
    if _LEGAL_CARD_RE.search(page_html):
        return _LEGAL_CARD_RE.sub(lambda match: f"{match.group(1)}\n      {content}\n    {match.group(3)}", page_html, count=1)
    if _LEGAL_MAIN_RE.search(page_html):
        return _LEGAL_MAIN_RE.sub(lambda match: f"{match.group(1)}\n      {content}\n    {match.group(3)}", page_html, count=1)
    return content


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
    page_html = path.read_text(encoding="utf-8")
    content = _extract_legal_content(page_html)
    return {
        "ok": True,
        "key": key,
        "title": LEGAL_DOCUMENTS[key]["title"],
        "content": content,
        "html": content,
        "url": "/terms/" if key == "terms" else f"/terms/{key}/",
    }


@router.put("/legal/{key}", dependencies=[Depends(require_superadmin_auth)])
async def admin_legal_update(key: LegalDocumentKey, payload: LegalDocumentPayload):
    path = _legal_path(key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="legal document file not found")
    content = _validate_legal_content(payload.html)
    page_html = path.read_text(encoding="utf-8")
    path.write_text(_replace_legal_content(page_html, content) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "key": key,
        "title": LEGAL_DOCUMENTS[key]["title"],
        "url": "/terms/" if key == "terms" else f"/terms/{key}/",
    }
