from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from aiogram.utils.web_app import safe_parse_webapp_init_data
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from server.core.loader import settings
from server.database.session import async_session
from server.database.models import (
    User,
    KeyStatus,
    SubscriptionPlan,
    Transaction,
)
from server.repositories.key_repository import KeyRepository
from server.repositories.server_repository import ServerRepository
from server.repositories.user_repository import UserRepository
from server.repositories.subscription_repository import SubscriptionRepository, NotEnoughBalanceError
from server.repositories.transaction_repository import TransactionRepository

from server.payments.generate_platega_invoice import PlategaPaymentAPI

router = APIRouter(prefix="/mini", tags=["mini-app"])

BOT_TOKEN = settings.BOT_TOKEN
if not BOT_TOKEN:
  raise RuntimeError("BOT_TOKEN is not set in settings")

XRAY_AUTH_TOKEN = settings.XRAY_AUTH

_platega_client: PlategaPaymentAPI | None = None


def platega() -> PlategaPaymentAPI:
  global _platega_client
  if _platega_client is None:
      _platega_client = PlategaPaymentAPI()
  return _platega_client


class InitPayload(BaseModel):
  initData: Optional[str] = None


class CreateKeyPayload(InitPayload):
  server_id: int
  label: str | None = None


class DeleteKeyPayload(InitPayload):
  key_id: int


class BuySubscriptionPayload(InitPayload):
  plan_id: int


class TopupPayload(InitPayload):
  amount: int


def _get_tg_user(init_data: Optional[str]) -> dict[str, Any]:
  """
  Берём пользователя из initData.
  Если initData нет или подпись некорректна — считаем, что приложение открыто не из Telegram.
  """
  if not init_data:
      raise HTTPException(401, "initData is missing. Откройте мини-приложение из Telegram.")

  try:
      parsed = safe_parse_webapp_init_data(BOT_TOKEN, init_data)
  except ValueError:
      raise HTTPException(401, "invalid initData signature")

  if not parsed.user:
      raise HTTPException(400, "no user in initData")

  user = parsed.user
  return {
      "id": user.id,
      "username": user.username,
      "first_name": getattr(user, "first_name", None),
      "last_name": getattr(user, "last_name", None),
      "photo_url": getattr(user, "photo_url", None),
  }


async def _get_vpn_user(session: AsyncSession, tg_id: int) -> User:
  res = await session.execute(select(User).where(User.tg_id == tg_id))
  user = res.scalar_one_or_none()

  if not user:
      raise HTTPException(404, "user not found, сначала зайдите в бота")

  return user


@router.post("/status")
async def mini_status(payload: InitPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)

      sub_repo = SubscriptionRepository(session)
      key_repo = KeyRepository(session)

      subscription = await sub_repo.get_active_subscription_with_plan_by_tg(tg_id)
      user_keys = await key_repo.get_keys_by_user_id(user.id)
      active_keys_cnt = sum(1 for k in user_keys if k.status == KeyStatus.active)

      if not subscription:
          return {
              "ok": False,
              "has_subscription": False,
              "statusText": f"Нет активной подписки. Активных ключей: {active_keys_cnt}",
              "active_keys": active_keys_cnt,
          }

      plan = subscription.plan
      status_text = (
          f"Тариф: {plan.name} • Ключей: {active_keys_cnt}/{plan.key_limit}\n"
          f"Подписка до: {subscription.current_period_end.strftime('%d.%m.%Y %H:%M')}"
      )

      return {
          "ok": True,
          "has_subscription": True,
          "statusText": status_text,
          "active_keys": active_keys_cnt,
          "plan": {
              "id": plan.id,
              "name": plan.name,
              "key_limit": plan.key_limit,
              "price": plan.price,
              "period_days": plan.period_days,
          },
      }


@router.post("/servers")
async def mini_servers(payload: InitPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)

      sub_repo = SubscriptionRepository(session)
      server_repo = ServerRepository(session)

      subscription = await sub_repo.get_active_subscription_with_plan_by_tg(tg_id)
      if not subscription:
          return {"ok": False, "reason": "no_subscription"}

      servers = await server_repo.get_all_servers()

      return {
          "ok": True,
          "servers": [
              {
                  "id": s.id,
                  "country": s.country.value if hasattr(s.country, "value") else str(s.country),
                  "public_host": s.public_host,
                  "note": s.note,
                  "created_at": s.created_at.isoformat() if s.created_at else None,
              }
              for s in servers
          ],
      }


@router.post("/keys/list")
async def mini_keys_list(payload: InitPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)
      key_repo = KeyRepository(session)

      keys = await key_repo.get_keys_by_user_id(user.id)

      return {
          "ok": True,
          "keys": [
              {
                  "id": k.id,
                  "uuid": k.uuid,
                  "uri": k.uri,
                  "status": k.status.value,
                  "server": (
                      k.server.country.value if (k.server and hasattr(k.server.country, "value"))
                      else (k.server.country if k.server else None)
                  ),
                  "created_at": k.created_at.isoformat() if k.created_at else None,
                  "expires_at": k.expires_at.isoformat() if k.expires_at else None,
              }
              for k in keys
              if k.status == KeyStatus.active
          ],
      }


@router.post("/keys/create")
async def mini_keys_create(payload: CreateKeyPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)
      sub_repo = SubscriptionRepository(session)
      server_repo = ServerRepository(session)
      key_repo = KeyRepository(session)

      subscription = await sub_repo.get_active_subscription_with_plan_by_tg(tg_id)
      if not subscription:
          raise HTTPException(403, "no active subscription")

      plan = subscription.plan

      user_keys = await key_repo.get_keys_by_user_id(user.id)
      active_keys_cnt = sum(1 for k in user_keys if k.status == KeyStatus.active)
      if active_keys_cnt >= plan.key_limit:
          raise HTTPException(403, f"key limit reached {active_keys_cnt}/{plan.key_limit}")

      existing = await key_repo.get_user_key_on_server(
          user.id,
          payload.server_id,
          [KeyStatus.active, KeyStatus.deleted],
      )
      if existing:
          raise HTTPException(403, "key on this server already exists")

      server = await server_repo.get_server_by_id(payload.server_id)
      if not server:
          raise HTTPException(404, "server not found")

      key = await key_repo.create_key(
          user_id=user.id,
          server=server,
          auth_token=XRAY_AUTH_TOKEN,
          label=payload.label,
      )

      return {
          "ok": True,
          "key": {
              "id": key.id,
              "uuid": key.uuid,
              "uri": key.uri,
              "server": (
                  server.country.value if hasattr(server.country, "value")
                  else server.country
              ) if server else None,
              "created_at": key.created_at.isoformat() if key.created_at else None,
              "expires_at": key.expires_at.isoformat() if key.expires_at else None,
          },
      }


@router.post("/keys/delete")
async def mini_keys_delete(payload: DeleteKeyPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)
      key_repo = KeyRepository(session)

      key = await key_repo.get_key_by_id(payload.key_id)
      if not key or key.user_id != user.id:
          raise HTTPException(404, "key not found")

      ok = await key_repo.delete_key(payload.key_id, auth_token=XRAY_AUTH_TOKEN)
      return {"ok": ok}


@router.post("/plans")
async def mini_plans(payload: InitPayload):
  _ = _get_tg_user(payload.initData)

  async with async_session() as session:
      result = await session.execute(select(SubscriptionPlan))
      plans = result.scalars().all()

      return {
          "ok": True,
          "plans": [
              {
                  "id": p.id,
                  "name": p.name,
                  "price": p.price,
                  "period_days": p.period_days,
                  "key_limit": p.key_limit,
                  "created_at": p.created_at.isoformat() if p.created_at else None,
              }
              for p in plans
          ],
      }


@router.post("/subscription/buy")
async def mini_subscription_buy(payload: BuySubscriptionPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      sub_repo = SubscriptionRepository(session)

      try:
          subscription = await sub_repo.create_or_renew_subscription(
              tg_id=tg_id,
              plan_id=payload.plan_id,
          )
      except NotEnoughBalanceError:
          raise HTTPException(status_code=402, detail="Not enough balance")

      result = await session.execute(
          select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
      )
      plan = result.scalar_one_or_none()
      if not plan:
          raise HTTPException(500, "plan not found after subscription creation")

      return {
          "ok": True,
          "subscription": {
              "id": subscription.id,
              "plan_id": plan.id,
              "plan_name": plan.name,
              "current_period_start": subscription.current_period_start.isoformat(),
              "current_period_end": subscription.current_period_end.isoformat(),
              "status": subscription.status.value,
          },
      }


@router.post("/profile")
async def mini_profile(payload: InitPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)

      tx_repo = TransactionRepository(session)
      txs = await tx_repo.get_transactions(tg_id)
      txs = txs[:10]

      return {
          "ok": True,
          "user": {
              "tg_id": user.tg_id,
              "username": user.username,
              "balance": user.balance,
              "created_at": user.created_at.isoformat() if user.created_at else None,
          },
          "transactions": [
              {
                  "id": t.id,
                  "amount": t.amount,
                  "payment_system": t.payment_system,
                  "order_id": t.order_id,
                  "paid": t.paid,
                  "created_at": t.created_at.isoformat() if t.created_at else None,
                  "paid_at": t.paid_at.isoformat() if t.paid_at else None,
                  "transaction_id": t.transaction_id,
              }
              for t in txs
          ],
      }


@router.post("/balance/topup")
async def mini_balance_topup(payload: TopupPayload):
  if payload.amount <= 0:
      raise HTTPException(400, "amount must be positive")

  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)

      amount = float(payload.amount)
      order_id = f"TPU-{tg_id}-{int(datetime.now().timestamp())}"

      resp = await platega().create_payment(
          amount=amount,
          currency="RUB",
          payment_method=2,
          description=f"Пополнение баланса на {amount} RUB",
          return_url="https://t.me/LunetVPNBot",
          failed_url="https://t.me/LunetVPNBot",
          payload=order_id,
      )

      http_status = resp.get("http_status", 200)
      if http_status >= 400:
          raise HTTPException(400, f"Platega HTTP {http_status}: {resp.get('error') or resp}")

      transaction_id: str | None = resp.get("transactionId")
      payment_url: str | None = resp.get("redirect") or resp.get("payformSuccessUrl")
      status: str | None = resp.get("status")

      if not transaction_id:
          raise HTTPException(500, "Platega: no transactionId in response")

      tx_repo = TransactionRepository(session)
      await tx_repo.create_transaction(
          tg_id=tg_id,
          transaction_id=transaction_id,
          amount=int(amount),
          payment_system="PLATEGA",
          order_id=order_id,
      )

      return {
          "ok": True,
          "payment_url": payment_url,
          "transaction_id": transaction_id,
          "status": status,
      }


@router.post("/balance/check")
async def mini_balance_check(payload: InitPayload):
  tg_user = _get_tg_user(payload.initData)
  tg_id = tg_user["id"]

  async with async_session() as session:
      user = await _get_vpn_user(session, tg_id)
      tx_repo = TransactionRepository(session)

      stmt = (
          select(Transaction)
          .join(User)
          .where(
              User.tg_id == tg_id,
              Transaction.paid.is_(False),
              Transaction.payment_system == "PLATEGA",
          )
          .order_by(Transaction.created_at.desc())
          .limit(1)
      )
      result = await session.execute(stmt)
      tx = result.scalar_one_or_none()

      if not tx:
          return {
              "ok": False,
              "reason": "no_pending",
              "message": "Нет незавершённых платежей",
          }

      resp = await platega().get_status(tx.transaction_id)
      http_status = resp.get("http_status", 200)
      if http_status == 404:
          raise HTTPException(404, "Platega: payment not found (404)")
      if http_status >= 400:
          raise HTTPException(400, f"Platega HTTP {http_status}: {resp.get('error') or resp}")

      status: str = (resp.get("status") or "").upper()

      if status == "CONFIRMED":
          if not tx.paid:
              await tx_repo.mark_transaction_as_paid(tx.transaction_id)
              user.balance = (user.balance or 0) + tx.amount
              await session.commit()
              await session.refresh(user)

          return {
              "ok": True,
              "transaction": {
                  "id": tx.id,
                  "transaction_id": tx.transaction_id,
                  "amount": tx.amount,
                  "paid": True,
                  "status_raw": status,
              },
              "balance": user.balance,
          }

      if status in {"CREATED", "PENDING", "INPROGRESS"}:
          return {
              "ok": True,
              "transaction": {
                  "id": tx.id,
                  "transaction_id": tx.transaction_id,
                  "amount": tx.amount,
                  "paid": False,
                  "status_raw": status,
              },
              "balance": user.balance,
          }

      if status in {"FAILED", "EXPIRED", "CANCELED"}:
          return {
              "ok": True,
              "transaction": {
                  "id": tx.id,
                  "transaction_id": tx.transaction_id,
                  "amount": tx.amount,
                  "paid": False,
                  "status_raw": status,
              },
              "balance": user.balance,
          }

      return {
          "ok": True,
          "transaction": {
              "id": tx.id,
              "transaction_id": tx.transaction_id,
              "amount": tx.amount,
              "paid": tx.paid,
              "status_raw": status or "UNKNOWN",
          },
          "balance": user.balance,
      }
