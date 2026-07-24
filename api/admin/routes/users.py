from aiogram import Bot
from decimal import Decimal
from fastapi import APIRouter
from ..common import *
from backend.core.loader import bot as runtime_bot
from backend.core.logger_config import logger
from backend.core.telegram import create_telegram_session

router = APIRouter()


def _activity_public(item) -> dict:
    return {
        "id": item.id,
        "category": item.category,
        "action": item.action,
        "source": item.source,
        "amount": int(item.amount or 0) if item.amount is not None else None,
        "traffic_gb": float(item.traffic_gb or 0) if item.traffic_gb is not None else None,
        "subscription_id": item.subscription_id,
        "transaction_id_ref": item.transaction_id_ref,
        "note": item.note,
        "created_at": _to_iso(item.created_at),
    }


async def _send_user_status_change_notification(*, tg_id: int, action: str) -> None:
    bot_instance = runtime_bot
    temp_bot: Bot | None = None
    if bot_instance is None:
        bot_token = (settings.BOT_TOKEN or "").strip()
        if not bot_token:
            logger.warning("[admin][users] status notify skipped: BOT_TOKEN missing")
            return
        session = create_telegram_session()
        temp_bot = Bot(token=bot_token, session=session)
        bot_instance = temp_bot

    text = (
        "⛔️ Ваш аккаунт заблокирован администратором. Для дополнительной информации свяжитесь со службой поддержки @LunetVPNSupport."
        if action == "ban"
        else "✅ Ваш аккаунт разблокирован."
    )
    try:
        await bot_instance.send_message(chat_id=tg_id, text=text)
    except Exception:
        logger.exception("[admin][users] status notify failed tg_id=%s action=%s", tg_id, action)
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()

@router.get("/users", dependencies=[Depends(require_support_auth)])
async def admin_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    banned: Literal["all", "only", "exclude"] = Query(default="all"),
):
    now = datetime.now(timezone.utc)
    offset = (page - 1) * page_size

    async with async_session() as session:
        active_sub_sq = (
            select(
                Subscription.user_id.label("user_id"),
                func.max(Subscription.current_period_end).label("subscription_end"),
            )
            .where(Subscription.status == SubStatus.active)
            .group_by(Subscription.user_id)
            .subquery()
        )

        active_keys_expr = literal("0", String)
        devices_expr = literal("0", String)
        sub_end_expr = active_sub_sq.c.subscription_end

        stmt = (
            select(
                User,
                active_keys_expr.label("active_keys_count"),
                devices_expr.label("devices_count"),
                sub_end_expr.label("subscription_end"),
            )
            .outerjoin(active_sub_sq, active_sub_sq.c.user_id == User.id)
        )
        count_stmt = select(func.count(User.id))

        if banned == "only":
            stmt = stmt.where(User.banned.is_(True))
            count_stmt = count_stmt.where(User.banned.is_(True))
        elif banned == "exclude":
            stmt = stmt.where(User.banned.is_(False))
            count_stmt = count_stmt.where(User.banned.is_(False))

        raw_search = (search or "").strip()
        if raw_search:
            pattern = f"%{raw_search}%"
            search_clause = or_(
                cast(User.tg_id, String).ilike(pattern),
                func.coalesce(User.username, "").ilike(pattern),
                func.coalesce(User.email, "").ilike(pattern),
            )
            stmt = stmt.where(search_clause)
            count_stmt = count_stmt.where(search_clause)

        sort_fields = {
            "id": User.id,
            "tg_id": User.tg_id,
            "username": func.lower(func.coalesce(User.username, "")),
            "email": func.lower(func.coalesce(User.email, "")),
            "balance": User.balance,
            "created_at": User.created_at,
            "updated_at": User.updated_at,
            "active_keys_count": active_keys_expr,
            "devices_count": devices_expr,
            "subscription_end": sub_end_expr,
        }
        sort_column = sort_fields.get(sort_by, User.created_at)
        if sort_by == "subscription_end":
            if sort_dir == "asc":
                sort_column = func.coalesce(sort_column, datetime(9999, 12, 31, tzinfo=timezone.utc))
            else:
                sort_column = func.coalesce(sort_column, datetime(1970, 1, 1, tzinfo=timezone.utc))

        order_by = desc(sort_column) if sort_dir == "desc" else sort_column.asc()

        total = int(await session.scalar(count_stmt) or 0)
        users = list(
            (await session.execute(stmt.order_by(order_by, User.id.desc()).offset(offset).limit(page_size))).all()
        )

        rows = []
        for user, _active_keys_count, _devices_count, subscription_end in users:
            sub_end = _as_aware_utc(subscription_end)
            rows.append(
                {
                    "id": user.id,
                    "tg_id": user.tg_id,
                    "username": user.username,
                    "email": user.email,
                    "balance": int(user.balance or 0),
                    "banned": bool(user.banned),
                    "subscription_token": None,
                    "active_keys_count": 0,
                    "devices_count": 0,
                    "subscription_active": bool(sub_end and sub_end > now),
                    "subscription_end": _to_iso(sub_end),
                    "created_at": _to_iso(user.created_at),
                    "updated_at": _to_iso(user.updated_at),
                }
            )

    return {
        "ok": True,
        "items": rows,
        "meta": {"page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size},
    }


@router.get("/users/{user_id}", dependencies=[Depends(require_support_auth)])
async def admin_user_details(user_id: int):
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = _http_404_if_none(await session.get(User, user_id), "user not found")
        subscription_service = SubscriptionService(session)
        activity_service = ActivityService(session)

        subscription = (
            await session.execute(
                select(Subscription, SubscriptionPlan.name)
                .join(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.current_period_end.desc())
                .limit(1)
            )
        ).first()
        sub = subscription[0] if subscription else None
        topup_gb = await subscription_service.get_topup_gb(sub.id) if sub else Decimal(0)

        txs = (
            await session.execute(select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.created_at.desc()).limit(25))
        ).scalars().all()
        activities = await activity_service.list_user_events(user_id=user_id, limit=100)
        topups = (
            await session.execute(
                select(SubscriptionTopup)
                .join(Subscription, Subscription.id == SubscriptionTopup.subscription_id)
                .where(Subscription.user_id == user_id)
                .order_by(SubscriptionTopup.created_at.desc(), SubscriptionTopup.id.desc())
                .limit(25)
            )
        ).scalars().all()

    sub = subscription[0] if subscription else None
    plan_name = subscription[1] if subscription else None
    sub_end = _as_aware_utc(sub.current_period_end) if sub else None

    return {
        "ok": True,
        "user": {
            "id": user.id,
            "tg_id": user.tg_id,
            "username": user.username,
            "email": user.email,
            "balance": int(user.balance or 0),
            "banned": bool(user.banned),
            "traffic_limit_bytes": int(user.traffic_limit_bytes or 0),
            "subscription_token": sub.subscription_token if sub else None,
            "created_at": _to_iso(user.created_at),
            "updated_at": _to_iso(user.updated_at),
        },
        "subscription": {
            "id": sub.id if sub else None,
            "plan_id": sub.plan_id if sub else None,
            "plan_name": plan_name,
            "status": sub.status.value if sub and sub.status else None,
            "current_period_start": _to_iso(sub.current_period_start) if sub else None,
            "current_period_end": _to_iso(sub_end),
            "active_now": bool(sub and sub.status == SubStatus.active and sub_end and sub_end > now),
            "auto_renew": bool(sub.auto_renew) if sub else None,
            "topup_gb": float(topup_gb or 0),
        },
        "keys": [],
        "devices": [],
        "transactions": [
            {
                "id": tx.id,
                "transaction_id": tx.transaction_id,
                "amount": int(tx.amount or 0),
                "payment_system": tx.payment_system,
                "paid": bool(tx.paid),
                "created_at": _to_iso(tx.created_at),
                "paid_at": _to_iso(tx.paid_at),
            }
            for tx in txs
        ],
        "topups": [
            {
                "id": item.id,
                "subscription_id": item.subscription_id,
                "gb": float(item.gb or 0),
                "created_at": _to_iso(item.created_at),
            }
            for item in topups
        ],
        "activities": [_activity_public(item) for item in activities],
    }


@router.post("/users/{user_id}/action", dependencies=[Depends(require_support_auth)])
async def admin_user_action(user_id: int, payload: UserActionPayload):
    async with async_session() as session:
        user = _http_404_if_none(await session.get(User, user_id), "user not found")
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        activity_service = ActivityService(session)
        remnawave_service = RemnaWaveService(session)

        try:
            if payload.action == "ban":
                user.banned = True
                await activity_service.log_user_event(
                    user_id=user_id,
                    category="admin",
                    action="ban",
                    source="admin_panel",
                    note="Пользователь заблокирован из админки",
                )
                if remnawave_service.enabled:
                    await remnawave_service.disable_user_access(user=user)
                await session.commit()
                if user.tg_id:
                    await _send_user_status_change_notification(tg_id=int(user.tg_id), action="ban")
                return {"ok": True, "action": payload.action}

            if payload.action == "unban":
                user.banned = False
                await activity_service.log_user_event(
                    user_id=user_id,
                    category="admin",
                    action="unban",
                    source="admin_panel",
                    note="Пользователь разблокирован из админки",
                )
                active_sub = (
                    await session.execute(
                        select(Subscription)
                        .where(Subscription.user_id == user_id)
                        .order_by(Subscription.current_period_end.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if remnawave_service.enabled and active_sub:
                    try:
                        await remnawave_service.enable_user_access(user=user, subscription=active_sub)
                        if active_sub.status == SubStatus.active:
                            await remnawave_service.sync_user_state(user=user, subscription=active_sub, status="ACTIVE")
                    except Exception:
                        logger.exception("[admin][users] remnawave re-enable failed user_id=%s", user_id)
                await session.commit()
                if user.tg_id:
                    await _send_user_status_change_notification(tg_id=int(user.tg_id), action="unban")
                return {"ok": True, "action": payload.action}

            if payload.action == "add_balance":
                amount = int(payload.amount or 0)
                if amount <= 0:
                    raise HTTPException(status_code=400, detail="amount must be > 0")
                await user_service.add_balance(user_id, amount)
                await activity_service.log_user_event(
                    user_id=user_id,
                    category="admin",
                    action="add_balance",
                    source="admin_panel",
                    amount=amount,
                    note="Ручное пополнение баланса из админки",
                )
                await session.refresh(user)
                await session.commit()
                return {"ok": True, "action": payload.action, "balance": int(user.balance or 0)}

            if payload.action == "sub_balance":
                amount = int(payload.amount or 0)
                if amount <= 0:
                    raise HTTPException(status_code=400, detail="amount must be > 0")
                await user_service.sub_balance(user_id, amount)
                await activity_service.log_user_event(
                    user_id=user_id,
                    category="admin",
                    action="sub_balance",
                    source="admin_panel",
                    amount=amount,
                    note="Ручное списание баланса из админки",
                )
                await session.refresh(user)
                await session.commit()
                return {"ok": True, "action": payload.action, "balance": int(user.balance or 0)}

            if payload.action == "add_traffic":
                gb = Decimal(str(payload.gb or 0))
                if gb <= 0:
                    raise HTTPException(status_code=400, detail="gb must be > 0")
                subscription = await subscription_service.add_traffic(user_id, gb)
                await activity_service.log_user_event(
                    user_id=user_id,
                    category="admin",
                    action="add_traffic",
                    source="admin_panel",
                    traffic_gb=gb,
                    subscription_id=subscription.id,
                    note="Ручная выдача трафика из админки",
                )
                await session.refresh(user)
                if remnawave_service.enabled:
                    await remnawave_service.sync_user_state(user=user, subscription=subscription, status="ACTIVE")
                await session.commit()
                topup_gb = await subscription_service.get_topup_gb(subscription.id)
                return {
                    "ok": True,
                    "action": payload.action,
                    "gb": float(gb),
                    "topup_gb": float(topup_gb or 0),
                    "traffic_limit_bytes": int(user.traffic_limit_bytes or 0),
                }

            raise HTTPException(status_code=400, detail="unsupported action")
        except HTTPException:
            raise
        except InsufficientBalance:
            raise HTTPException(status_code=400, detail="insufficient balance")
        except (BannedUser, UserNotFound, SubscriptionNotFound) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


