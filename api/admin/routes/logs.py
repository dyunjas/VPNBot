from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..common import Query, require_admin_auth

router = APIRouter()

BASE_LOG_DIR = Path("logs").resolve()


def _safe_log_path(filename: str) -> Path:
    candidate = (BASE_LOG_DIR / filename).resolve()
    if candidate.parent != BASE_LOG_DIR:
        raise HTTPException(status_code=400, detail="invalid log filename")
    return candidate


@router.get("/logs", dependencies=[Depends(require_admin_auth)])
async def admin_logs_list(
    limit: int = Query(default=100, ge=1, le=500),
):
    if not BASE_LOG_DIR.exists():
        return {"ok": True, "items": []}

    files = [
        p
        for p in BASE_LOG_DIR.iterdir()
        if p.is_file()
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    items = []
    for p in files[:limit]:
        stat = p.stat()
        items.append(
            {
                "filename": p.name,
                "size_bytes": int(stat.st_size),
                "updated_at": int(stat.st_mtime),
                "download_url": f"/api/admin/logs/{p.name}/download",
            }
        )
    return {"ok": True, "items": items}


@router.get("/logs/{filename}/download", dependencies=[Depends(require_admin_auth)])
async def admin_logs_download(filename: str):
    path = _safe_log_path(filename)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="log file not found")
    return FileResponse(
        path=path,
        media_type="text/plain; charset=utf-8",
        filename=path.name,
    )
