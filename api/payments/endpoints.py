from __future__ import annotations

import json
from urllib.parse import parse_qs

from aiogram import Bot
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from api.bot.common import _apply_referral_reward
from backend.core.config import settings
from backend.core.logger_config import logger
from backend.core.telegram import create_telegram_session
from backend.database.session import async_session
from backend.services import BillingService, UserService
from backend.services.exceptions import PaymentNotConfirmed, TransactionNotFound, UserNotFound

router = APIRouter(tags=["payments"])


def _first(values: dict[str, list[str]], key: str) -> str:
    raw = values.get(key) or [""]
    return str(raw[0] or "").strip()


async def _notify_payment(tx, *, referral_bonus: int = 0, referrer_tg_id: int | None = None) -> None:
    if not settings.BOT_TOKEN:
        return
    async with async_session() as session:
        user_service = UserService(session)
        try:
            user = await user_service.get_by_id(int(tx.user_id))
        except UserNotFound:
            return

    session = create_telegram_session()
    bot = Bot(token=settings.BOT_TOKEN, session=session)
    try:
        await bot.send_message(
            chat_id=int(user.tg_id),
            text=(
                "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> "
                "<b>Платеж подтвержден</b>\n"
                f"Баланс пополнен на <b>{int(tx.amount or 0)} RUB</b>."
            ),
            parse_mode="HTML",
        )
        if referral_bonus > 0 and referrer_tg_id:
            await bot.send_message(
                chat_id=int(referrer_tg_id),
                text=(
                    "<tg-emoji emoji-id='5994502837327892086'>🎉</tg-emoji> "
                    "<b>Бонус за реферала!</b>\n"
                    f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Начислено: <b>{int(referral_bonus)} RUB</b>\n"
                    f"<tg-emoji emoji-id='5769403330761593044'>💄</tg-emoji> Платеж реферала: <b>{int(tx.amount or 0)} RUB</b>"
                ),
                parse_mode="HTML",
            )
    except Exception as e:
        logger.warning(
            "[payments] notify_user_failed user_id=%s tg_id=%s error=%s",
            getattr(user, "id", None),
            getattr(user, "tg_id", None),
            e,
        )
    finally:
        await bot.session.close()


async def _handle_pal24_postback(request: Request) -> JSONResponse:
    body = (await request.body()).decode("utf-8", errors="replace")
    form = parse_qs(body, keep_blank_values=True)

    inv_id = _first(form, "InvId")
    out_sum = _first(form, "OutSum")
    status = _first(form, "Status")
    signature = _first(form, "SignatureValue")
    trs_id = _first(form, "TrsId")

    if not inv_id or not out_sum or not status or not signature:
        logger.warning("[payments][pal24] missing_required_fields inv_id=%s trs_id=%s", inv_id, trs_id)
        return JSONResponse(status_code=400, content={"ok": False, "detail": "missing required fields"})

    if not BillingService.verify_pally_postback_signature(
        inv_id=inv_id,
        out_sum=out_sum,
        signature=signature,
    ):
        logger.warning("[payments][pal24] invalid_signature inv_id=%s trs_id=%s", inv_id, trs_id)
        return JSONResponse(status_code=403, content={"ok": False, "detail": "invalid signature"})

    async with async_session() as session:
        billing = BillingService(session)
        try:
            tx, credited = await billing.confirm_pally_postback(
                inv_id=inv_id,
                out_sum=out_sum,
                status=status,
                trs_id=trs_id,
            )
            reward = {"bonus": 0}
            if credited:
                reward = await _apply_referral_reward(
                    session=session,
                    transaction_user_id=int(tx.user_id),
                    amount=int(tx.amount or 0),
                )
        except TransactionNotFound:
            return JSONResponse(status_code=404, content={"ok": False, "detail": "transaction not found"})
        except PaymentNotConfirmed as e:
            return JSONResponse(status_code=200, content={"ok": True, "confirmed": False, "detail": str(e)})
        finally:
            await billing.close_clients()

    if credited:
        await _notify_payment(
            tx,
            referral_bonus=int(reward.get("bonus") or 0),
            referrer_tg_id=reward.get("referrer_tg_id"),
        )

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "confirmed": bool(getattr(tx, "paid", False) or credited),
            "credited": bool(credited),
        },
    )


@router.post("/api/payments/pal24-webhook")
async def pal24_postback_api(request: Request):
    return await _handle_pal24_postback(request)

async def _handle_platega_webhook(request: Request) -> Response:
    merchant_id = request.headers.get("X-MerchantId")
    secret = request.headers.get("X-Secret")
    if not BillingService.verify_platega_webhook_headers(merchant_id=merchant_id, secret=secret):
        logger.warning("[payments][platega] invalid_headers merchant_id=%s", merchant_id)
        return JSONResponse(status_code=403, content={"ok": False, "detail": "invalid credentials"})

    try:
        data = await request.json()
    except Exception:
        logger.warning("[payments][platega] invalid_json")
        return JSONResponse(status_code=400, content={"ok": False, "detail": "invalid json"})

    provider_id = str(data.get("id") or "").strip()
    amount = data.get("amount")
    currency = str(data.get("currency") or "").strip()
    status = str(data.get("status") or "").strip()
    payload = data.get("payload")
    payment_method = data.get("paymentMethod")
    try:
        payment_method_value = int(payment_method) if payment_method is not None else None
    except (TypeError, ValueError):
        payment_method_value = None

    if not provider_id or amount is None or not currency or not status:
        logger.warning("[payments][platega] missing_required_fields provider_id=%s status=%s", provider_id, status)
        return JSONResponse(status_code=400, content={"ok": False, "detail": "missing required fields"})

    async with async_session() as session:
        billing = BillingService(session)
        try:
            tx, credited = await billing.confirm_platega_webhook(
                provider_transaction_id=provider_id,
                amount=amount,
                currency=currency,
                status=status,
                payload=str(payload or ""),
                payment_method=payment_method_value,
            )
            reward = {"bonus": 0}
            if credited:
                reward = await _apply_referral_reward(
                    session=session,
                    transaction_user_id=int(tx.user_id),
                    amount=int(tx.amount or 0),
                )
        except TransactionNotFound:
            return JSONResponse(status_code=404, content={"ok": False, "detail": "transaction not found"})
        except PaymentNotConfirmed:
            return Response(status_code=200)
        finally:
            await billing.close_clients()

    if credited:
        await _notify_payment(
            tx,
            referral_bonus=int(reward.get("bonus") or 0),
            referrer_tg_id=reward.get("referrer_tg_id"),
        )

    return Response(status_code=200)


@router.post("/api/payments/platega-webhook")
async def platega_webhook_api(request: Request):
    return await _handle_platega_webhook(request)

async def _handle_cryptobot_webhook(request: Request) -> Response:
    body = await request.body()
    signature = request.headers.get("crypto-pay-api-signature")
    if not BillingService.verify_crypto_webhook_signature(body=body, signature=signature):
        logger.warning("[payments][cryptobot] invalid_signature")
        return JSONResponse(status_code=403, content={"ok": False, "detail": "invalid signature"})

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        logger.warning("[payments][cryptobot] invalid_json")
        return JSONResponse(status_code=400, content={"ok": False, "detail": "invalid json"})

    update_type = str(data.get("update_type") or "").strip()
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    invoice_id = payload.get("invoice_id")
    status = payload.get("status")

    if update_type != "invoice_paid":
        logger.info("[payments][cryptobot] ignored_update update_type=%s", update_type)
        return Response(status_code=200)

    try:
        invoice_id_int = int(invoice_id)
    except (TypeError, ValueError):
        logger.warning("[payments][cryptobot] missing_invoice_id invoice_id=%s", invoice_id)
        return JSONResponse(status_code=400, content={"ok": False, "detail": "missing invoice_id"})

    async with async_session() as session:
        billing = BillingService(session)
        try:
            tx, credited = await billing.confirm_crypto_webhook(
                invoice_id=invoice_id_int,
                status=str(status or ""),
                update_type=update_type,
            )
            reward = {"bonus": 0}
            if credited:
                reward = await _apply_referral_reward(
                    session=session,
                    transaction_user_id=int(tx.user_id),
                    amount=int(tx.amount or 0),
                )
        except TransactionNotFound:
            return JSONResponse(status_code=404, content={"ok": False, "detail": "transaction not found"})
        except PaymentNotConfirmed:
            return Response(status_code=200)
        finally:
            await billing.close_clients()

    if credited:
        await _notify_payment(
            tx,
            referral_bonus=int(reward.get("bonus") or 0),
            referrer_tg_id=reward.get("referrer_tg_id"),
        )

    return Response(status_code=200)


@router.post("/api/payments/cryptobot-webhook")
async def cryptobot_webhook_api(request: Request):
    return await _handle_cryptobot_webhook(request)
