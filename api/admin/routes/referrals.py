from fastapi import APIRouter
from ..common import *

router = APIRouter()

@router.get("/referrals", dependencies=[Depends(require_admin_auth)])
async def admin_referrals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    search: str | None = Query(default=None),
):
    offset = (page - 1) * page_size
    async with async_session() as session:
        stmt = select(ReferralAccount, User.tg_id, User.username).join(User, User.id == ReferralAccount.user_id)
        count_stmt = select(func.count(ReferralAccount.id))

        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            clause = or_(
                cast(ReferralAccount.user_id, String).ilike(pattern),
                cast(User.tg_id, String).ilike(pattern),
                func.coalesce(User.username, "").ilike(pattern),
            )
            stmt = stmt.where(clause)
            count_stmt = count_stmt.join(User, User.id == ReferralAccount.user_id).where(clause)

        total = int(await session.scalar(count_stmt) or 0)
        rows = (
            await session.execute(
                stmt.order_by(ReferralAccount.created_at.desc()).offset(offset).limit(page_size)
            )
        ).all()

    return {
        "ok": True,
        "items": [
            {
                "id": acc.id,
                "user_id": acc.user_id,
                "tg_id": tg_id,
                "username": username,
                "invited_count": int(acc.invited_count or 0),
                "referral_balance": int(acc.referral_balance or 0),
                "referral_percent": int(acc.referral_percent or 0),
                "created_at": _to_iso(acc.created_at),
            }
            for acc, tg_id, username in rows
        ],
        "meta": {"page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size},
    }


@router.patch("/referrals/{account_id}", dependencies=[Depends(require_admin_auth)])
async def admin_referral_update(
    account_id: int,
    referral_percent: int | None = Query(default=None, ge=0, le=100),
    referral_balance: int | None = Query(default=None, ge=0),
):
    async with async_session() as session:
        acc = _http_404_if_none(await session.get(ReferralAccount, account_id), "referral account not found")
        if referral_percent is not None:
            acc.referral_percent = referral_percent
        if referral_balance is not None:
            acc.referral_balance = referral_balance
        await session.commit()
        await session.refresh(acc)
        return {
            "ok": True,
            "account": {
                "id": acc.id,
                "user_id": acc.user_id,
                "referral_percent": int(acc.referral_percent or 0),
                "referral_balance": int(acc.referral_balance or 0),
            },
        }
