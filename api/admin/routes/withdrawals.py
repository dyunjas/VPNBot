from aiogram import Bot
from fastapi import APIRouter
from ..common import *
from backend.core import loader as bot_loader
from backend.core.telegram import create_telegram_session

router = APIRouter()


async def _notify_withdrawal(*, tg_id: int, withdrawal_id: int, amount: int, approved: bool) -> None:
    bot_instance = bot_loader.bot
    temporary_bot = None
    if bot_instance is None:
        token = (settings.BOT_TOKEN or "").strip()
        if not token:
            return
        temporary_bot = Bot(token=token, session=create_telegram_session())
        bot_instance = temporary_bot
    try:
        if approved:
            text = (
                "✅ <b>Ваш вывод подтверждён</b>\n\n"
                f"ID заявки: <code>{withdrawal_id}</code>\n"
                f"Сумма: <b>{amount} RUB</b>"
            )
        else:
            text = (
                "❗️ <b>Ваш вывод отклонён</b>\n\n"
                f"ID заявки: <code>{withdrawal_id}</code>\n"
                f"Сумма: <b>{amount} RUB</b>\n\n"
                "Средства возвращены на ваш реферальный баланс."
            )
        await bot_instance.send_message(chat_id=tg_id, text=text, parse_mode="HTML")
    except Exception:
        return
    finally:
        if temporary_bot is not None:
            await temporary_bot.session.close()

@router.get("/withdrawals", dependencies=[Depends(require_superadmin_auth)])
async def admin_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    status: Literal["all", "pending", "approved", "rejected"] = Query(default="all"),
    search: str | None = Query(default=None),
):
    offset = (page - 1) * page_size
    async with async_session() as session:
        stmt = (
            select(ReferralWithdrawal, ReferralAccount.user_id, User.tg_id, User.username)
            .join(ReferralAccount, ReferralAccount.id == ReferralWithdrawal.referral_account_id)
            .join(User, User.id == ReferralAccount.user_id)
        )
        count_stmt = select(func.count(ReferralWithdrawal.id))

        if status != "all":
            st = WithdrawalStatus(status)
            stmt = stmt.where(ReferralWithdrawal.status == st)
            count_stmt = count_stmt.where(ReferralWithdrawal.status == st)

        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            search_clause = or_(
                cast(ReferralWithdrawal.id, String).ilike(pattern),
                cast(ReferralAccount.user_id, String).ilike(pattern),
                cast(User.tg_id, String).ilike(pattern),
                func.coalesce(User.username, "").ilike(pattern),
                func.coalesce(ReferralWithdrawal.method, "").ilike(pattern),
            )
            stmt = stmt.where(search_clause)
            count_stmt = count_stmt.join(ReferralAccount, ReferralAccount.id == ReferralWithdrawal.referral_account_id).join(User, User.id == ReferralAccount.user_id).where(search_clause)

        total = int(await session.scalar(count_stmt) or 0)
        rows = (
            await session.execute(
                stmt.order_by(ReferralWithdrawal.created_at.desc()).offset(offset).limit(page_size)
            )
        ).all()

    return {
        "ok": True,
        "items": [
            {
                "id": w.id,
                "user_id": user_id,
                "tg_id": tg_id,
                "username": username,
                "amount": int(w.amount or 0),
                "method": w.method,
                "status": w.status.value if w.status else None,
                "created_at": _to_iso(w.created_at),
            }
            for w, user_id, tg_id, username in rows
        ],
        "meta": {"page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size},
    }


@router.post("/withdrawals/{withdrawal_id}/{action}", dependencies=[Depends(require_superadmin_auth)])
async def admin_withdrawal_action(withdrawal_id: int, action: Literal["approve", "reject"]):
    async with async_session() as session:
        w = _http_404_if_none(await session.get(ReferralWithdrawal, withdrawal_id), "withdrawal not found")
        if w.status != WithdrawalStatus.pending:
            raise HTTPException(status_code=400, detail="withdrawal already processed")

        if action == "approve":
            w.status = WithdrawalStatus.approved
            account = _http_404_if_none(await session.get(ReferralAccount, w.referral_account_id), "ref account not found")
            user = await session.get(User, account.user_id)
            await session.commit()
            if user and getattr(user, "tg_id", None):
                await _notify_withdrawal(tg_id=int(user.tg_id), withdrawal_id=withdrawal_id, amount=int(w.amount or 0), approved=True)
            return {"ok": True, "status": w.status.value}

        w.status = WithdrawalStatus.rejected
        account = _http_404_if_none(await session.get(ReferralAccount, w.referral_account_id), "ref account not found")
        account.referral_balance = int(account.referral_balance or 0) + int(w.amount or 0)
        user = await session.get(User, account.user_id)
        await session.commit()
        if user and getattr(user, "tg_id", None):
            await _notify_withdrawal(tg_id=int(user.tg_id), withdrawal_id=withdrawal_id, amount=int(w.amount or 0), approved=False)
        return {"ok": True, "status": w.status.value}


