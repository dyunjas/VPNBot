from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

from ..common import *

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGS_DIR = PROJECT_ROOT / "logs"
ERROR_LINE_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s*\|\s*(?P<level>ERROR|CRITICAL|WARNING)\s*\|\s*(?P<logger>[^|]*)\|\s*(?P<message>.*)$"
)
SIMPLE_ERROR_RE = re.compile(r"(?P<level>ERROR|CRITICAL)\s*[:| -]\s*(?P<message>.*)", re.IGNORECASE)


def _read_tail(path: Path, max_bytes: int = 700_000) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _normalize_error_message(message: str) -> str:
    text = re.sub(r"\s+", " ", message or "").strip()
    text = re.sub(r"\b(user_id|sub_id|subscription_id|chat_id|tg_id|id)=\d+", r"\1=*", text)
    text = re.sub(r"#\d+", "#*", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T ][\d:.+-]+", "*date*", text)
    return text[:260] or "Unknown error"


def _parse_error_rows(limit_per_file: int = 300) -> list[dict]:
    if not LOGS_DIR.exists():
        return []

    rows: list[dict] = []
    for path in sorted(LOGS_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        text = _read_tail(path)
        if not text:
            continue
        lines = text.splitlines()[-limit_per_file:]
        for idx, line in enumerate(lines):
            parsed = ERROR_LINE_RE.match(line)
            if parsed:
                rows.append(
                    {
                        "file": path.name,
                        "line": idx + 1,
                        "level": parsed.group("level"),
                        "logger": parsed.group("logger").strip(),
                        "message": parsed.group("message").strip(),
                        "time": parsed.group("time"),
                    }
                )
                continue

            if "Traceback" in line or "Exception" in line or "ERROR" in line or "CRITICAL" in line:
                simple = SIMPLE_ERROR_RE.search(line)
                rows.append(
                    {
                        "file": path.name,
                        "line": idx + 1,
                        "level": (simple.group("level").upper() if simple else "ERROR"),
                        "logger": "",
                        "message": (simple.group("message").strip() if simple else line.strip())[:900],
                        "time": None,
                    }
                )
    return rows


@router.get("/diagnostics/errors", dependencies=[Depends(require_superadmin_auth)])
async def admin_diagnostics_errors(limit: int = Query(default=40, ge=1, le=200)):
    rows = _parse_error_rows()
    grouped: dict[str, dict] = {}
    for row in rows:
        key = f"{row['file']}::{_normalize_error_message(row['message'])}"
        item = grouped.setdefault(
            key,
            {
                "key": key,
                "file": row["file"],
                "level": row["level"],
                "message": _normalize_error_message(row["message"]),
                "count": 0,
                "last_time": row["time"],
                "examples": [],
            },
        )
        item["count"] += 1
        if row["time"]:
            item["last_time"] = row["time"]
        if len(item["examples"]) < 3:
            item["examples"].append(row)

    items = sorted(grouped.values(), key=lambda x: (x.get("last_time") or "", x["count"]), reverse=True)[:limit]
    total = sum(item["count"] for item in grouped.values())
    return {
        "ok": True,
        "summary": {
            "groups": len(grouped),
            "events": total,
            "files": len({row["file"] for row in rows}),
        },
        "items": items,
    }


@router.get("/diagnostics/auto-renewals", dependencies=[Depends(require_superadmin_auth)])
async def admin_diagnostics_auto_renewals(
    days: int = Query(default=7, ge=1, le=60),
    limit: int = Query(default=100, ge=1, le=300),
):
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days)

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Subscription, User, SubscriptionPlan)
                .join(User, User.id == Subscription.user_id)
                .outerjoin(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id)
                .where(Subscription.auto_renew.is_(True))
                .where(Subscription.current_period_end <= until)
                .order_by(Subscription.current_period_end.asc())
                .limit(limit)
            )
        ).all()

        recent_events = (
            await session.execute(
                select(UserActivity, User.tg_id, User.username)
                .join(User, User.id == UserActivity.user_id)
                .where(
                    or_(
                        UserActivity.action.ilike("%auto_renew%"),
                        UserActivity.note.ilike("%auto%renew%"),
                        UserActivity.note.ilike("%автопрод%"),
                    )
                )
                .order_by(UserActivity.created_at.desc())
                .limit(50)
            )
        ).all()

    queue = []
    stats = defaultdict(int)
    for sub, user, plan in rows:
        end = _as_aware_utc(sub.current_period_end)
        reason = "ready"
        if user.banned:
            reason = "user_banned"
        elif sub.status != SubStatus.active:
            reason = "subscription_not_active"
        elif plan is None:
            reason = "plan_not_found"
        elif int(user.balance or 0) < int(plan.price or 0):
            reason = "insufficient_balance"
        elif end and end > now:
            reason = "scheduled"

        stats[reason] += 1
        queue.append(
            {
                "subscription_id": sub.id,
                "user_id": user.id,
                "tg_id": user.tg_id,
                "username": user.username,
                "plan_id": sub.plan_id,
                "plan_name": plan.name if plan else None,
                "plan_price": int(plan.price or 0) if plan else None,
                "balance": int(user.balance or 0),
                "status": sub.status.value if sub.status else None,
                "auto_renew": bool(sub.auto_renew),
                "current_period_end": _to_iso(sub.current_period_end),
                "next_renewal_at": _to_iso(sub.next_renewal_at),
                "reason": reason,
            }
        )

    return {
        "ok": True,
        "summary": {
            "days": days,
            "total": len(queue),
            "ready": stats["ready"],
            "scheduled": stats["scheduled"],
            "problem": len(queue) - stats["ready"] - stats["scheduled"],
            "by_reason": dict(stats),
        },
        "items": queue,
        "events": [
            {
                "id": event.id,
                "user_id": event.user_id,
                "tg_id": tg_id,
                "username": username,
                "action": event.action,
                "source": event.source,
                "subscription_id": event.subscription_id,
                "amount": int(event.amount or 0) if event.amount is not None else None,
                "note": event.note,
                "created_at": _to_iso(event.created_at),
            }
            for event, tg_id, username in recent_events
        ],
    }
