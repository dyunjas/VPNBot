from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from backend.database.models import LegalDocument
from backend.database.session import async_session

LEGAL_DIR = Path(__file__).resolve().parents[2] / "frontend" / "static" / "legal"

LegalDocumentKey = Literal["terms", "privacy", "offer"]

LEGAL_DOCUMENTS: dict[str, dict[str, str]] = {
    "terms": {"title": "Пользовательское соглашение", "filename": "terms.html"},
    "privacy": {"title": "Политика конфиденциальности", "filename": "privacy.html"},
    "offer": {"title": "Оферта", "filename": "offer.html"},
}


class LegalDocumentPayload(BaseModel):
    html: str = Field(min_length=1, max_length=250_000)
    revision: int | None = Field(default=None, ge=0)


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
    _LegalValidator().feed(html)
    return html


class _LegalValidator(HTMLParser):
    """Allow static document markup; inspect decoded attributes, including unquoted URLs."""
    tags = {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "b", "em", "i", "u", "br", "hr", "a", "span", "blockquote", "table", "thead", "tbody", "tr", "td", "th", "caption", "dl", "dt", "dd", "sup", "sub", "small", "code", "pre"}
    attributes = {"href", "title", "class", "id", "target", "rel", "colspan", "rowspan"}

    def handle_starttag(self, tag, attrs):
        if tag not in self.tags:
            raise HTTPException(400, "Unsupported document markup")
        for name, value in attrs:
            if name not in self.attributes or value is None:
                raise HTTPException(400, "Unsupported document attribute")
            if name == "href":
                clean = "".join(c for c in value if ord(c) > 32).strip()
                if urlsplit(clean).scheme.lower() not in {"", "https", "http", "mailto"}:
                    raise HTTPException(400, "Unsafe document link")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag not in self.tags:
            raise HTTPException(400, "Unsupported document markup")


def _replace_legal_content(page_html: str, content: str) -> str:
    if _LEGAL_CARD_RE.search(page_html):
        return _LEGAL_CARD_RE.sub(lambda match: f"{match.group(1)}\n      {content}\n    {match.group(3)}", page_html, count=1)
    if _LEGAL_MAIN_RE.search(page_html):
        return _LEGAL_MAIN_RE.sub(lambda match: f"{match.group(1)}\n      {content}\n    {match.group(3)}", page_html, count=1)
    return content


def _page_template(key: str) -> str:
    path = _legal_path(key)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{LEGAL_DOCUMENTS[key]["title"]} — Lunet</title><link rel="stylesheet" href="/miniapp/legal/legal.css"></head><body><header class="legal-header"><a href="https://lunet.pro/">Lunet</a><a href="https://app.lunet.pro/cabinet/">В кабинет</a></header><nav class="document-nav"><a href="/terms/">Соглашение</a><a href="/terms/privacy/">Конфиденциальность</a><a href="/terms/offer/">Оферта</a></nav><main class="page"><section class="card"></section></main></body></html>'''


async def get_legal_document(key: str) -> dict:
    path = _legal_path(key)
    async with async_session() as session:
        document = await session.get(LegalDocument, key)
        if document:
            content, revision, updated = document.html, document.revision, document.updated_at.isoformat()
        elif path.is_file():
            content = _extract_legal_content(path.read_text(encoding="utf-8"))
            revision, updated = 0, None
        else:
            raise HTTPException(404, "Текст документа пока не опубликован")
    return {"ok": True, "key": key, "title": LEGAL_DOCUMENTS[key]["title"], "content": content, "html": content, "revision": revision, "updated_at": updated, "url": "/terms/" if key == "terms" else f"/terms/{key}/"}


async def update_legal_document(key: str, payload: LegalDocumentPayload) -> dict:
    _legal_path(key)
    content = _validate_legal_content(payload.html)
    if not content:
        raise HTTPException(400, "Документ не должен быть пустым")
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        if payload.revision == 0:
            statement = insert(LegalDocument).values(key=key, html=content, revision=1, updated_at=now).on_conflict_do_nothing(index_elements=[LegalDocument.key])
        elif payload.revision is not None:
            statement = update(LegalDocument).where(LegalDocument.key == key, LegalDocument.revision == payload.revision).values(html=content, revision=LegalDocument.revision + 1, updated_at=now)
        else:
            statement = insert(LegalDocument).values(key=key, html=content, revision=1, updated_at=now).on_conflict_do_update(index_elements=[LegalDocument.key], set_={"html": content, "revision": LegalDocument.revision + 1, "updated_at": now})
        revision = (await session.execute(statement.returning(LegalDocument.revision))).scalar_one_or_none()
        if revision is None:
            raise HTTPException(409, "Документ изменён в другом окне. Обновите текст перед сохранением.")
        await session.commit()
    return {"ok": True, "key": key, "revision": revision, "updated_at": now.isoformat(), "url": "/terms/" if key == "terms" else f"/terms/{key}/"}


async def render_legal_document(key: str) -> str:
    document = await get_legal_document(key)
    return _replace_legal_content(_page_template(key), document["content"])


