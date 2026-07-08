from datetime import datetime, timezone

from fastapi import APIRouter

from ..common import *

router = APIRouter()


@router.get("/transactions", dependencies=[Depends(require_admin_auth)])
async def admin_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    paid: Literal["all", "paid", "unpaid"] = Query(default="all"),
    payment_system: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
):
    sort_column = TX_SORT_FIELDS.get(sort_by, Transaction.created_at)
    order_by = desc(sort_column) if sort_dir == "desc" else sort_column.asc()
    offset = (page - 1) * page_size

    async with async_session() as session:
        stmt = select(Transaction, User.tg_id, User.username).join(User, User.id == Transaction.user_id)
        count_stmt = select(func.count(Transaction.id))

        if paid == "paid":
            stmt = stmt.where(Transaction.paid.is_(True))
            count_stmt = count_stmt.where(Transaction.paid.is_(True))
        elif paid == "unpaid":
            stmt = stmt.where(Transaction.paid.is_(False))
            count_stmt = count_stmt.where(Transaction.paid.is_(False))

        if payment_system:
            ps = payment_system.strip()
            stmt = stmt.where(Transaction.payment_system == ps)
            count_stmt = count_stmt.where(Transaction.payment_system == ps)

        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            search_clause = or_(
                cast(Transaction.id, String).ilike(pattern),
                cast(Transaction.user_id, String).ilike(pattern),
                cast(User.tg_id, String).ilike(pattern),
                func.coalesce(User.username, "").ilike(pattern),
                func.coalesce(Transaction.transaction_id, "").ilike(pattern),
            )
            stmt = stmt.where(search_clause)
            count_stmt = count_stmt.join(User, User.id == Transaction.user_id).where(search_clause)

        total = int(await session.scalar(count_stmt) or 0)
        rows = (await session.execute(stmt.order_by(order_by).offset(offset).limit(page_size))).all()

    return {
        "ok": True,
        "items": [
            {
                "id": tx.id,
                "user_id": tx.user_id,
                "tg_id": tg_id,
                "username": username,
                "transaction_id": tx.transaction_id,
                "amount": int(tx.amount or 0),
                "payment_system": tx.payment_system,
                "paid": bool(tx.paid),
                "created_at": _to_iso(tx.created_at),
                "paid_at": _to_iso(tx.paid_at),
            }
            for tx, tg_id, username in rows
        ],
        "meta": {"page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size},
    }


@router.post("/transactions/{transaction_id}/confirm", dependencies=[Depends(require_admin_auth)])
async def admin_transaction_confirm(transaction_id: int):
    async with async_session() as session:
        tx = _http_404_if_none(await session.get(Transaction, transaction_id), "transaction not found")
        user = _http_404_if_none(await session.get(User, tx.user_id), "user not found")
        if bool(tx.paid):
            return {
                "ok": True,
                "transaction_id": tx.id,
                "already_paid": True,
                "balance": int(user.balance or 0),
            }

        user.balance = int(user.balance or 0) + int(tx.amount or 0)
        tx.paid = True
        tx.paid_at = datetime.now(timezone.utc)

        await ActivityService(session).log_user_event(
            user_id=user.id,
            category="admin",
            action="payment_confirmed",
            source="admin_panel",
            amount=int(tx.amount or 0),
            transaction_id_ref=tx.id,
            note=f"Ручное подтверждение платежа {tx.transaction_id or tx.id}",
        )
        await session.commit()
        await session.refresh(user)
        return {
            "ok": True,
            "transaction_id": tx.id,
            "already_paid": False,
            "balance": int(user.balance or 0),
            "paid_at": _to_iso(tx.paid_at),
        }
