from fastapi import APIRouter

from ..common import *
from backend.core.business_config import get_business_int

router = APIRouter()


def _public_payment_method(payment_system: str) -> str:
    raw = str(payment_system or "").lower().strip()
    if raw == "cryptobot":
        return "crypto"
    if raw in ("platega", "pally"):
        return raw
    return raw


async def _confirm_transaction_by_method(
    billing: BillingService,
    method: str,
    provider_id: str,
) -> None:
    if method == "platega":
        await billing.confirm_platega_payment(provider_id)
        return
    if method == "pally":
        await billing.confirm_pally_payment(provider_id)
        return
    if method == "crypto":
        await billing.confirm_crypto_payment(int(provider_id))
        return
    raise HTTPException(400, "method must be 'platega', 'crypto' or 'pally'")


@router.post("/promocode/apply")
async def mini_promocode_apply(payload: ApplyPromocodePayload):
    code = (payload.code or "").strip()
    if not code:
        raise HTTPException(400, "Введите промокод")

    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        promo_service = PromoService(session)
        try:
            promo = await promo_service.activate_promocode(user_id=user.id, code=code)
        except Exception as e:
            raise _map_service_error(e)

        user_service = UserService(session)
        fresh_user = await user_service.get_by_id(user.id)

        return {
            "ok": True,
            "amount_added": int(promo.amount or 0),
            "balance": fresh_user.balance,
        }


@router.post("/balance/topup")
async def mini_balance_topup(payload: TopupPayload):
    if payload.amount <= 0:
        raise HTTPException(400, "Сумма должна быть больше нуля")

    method = (payload.method or "platega").lower().strip()
    if method not in ("platega", "crypto", "pally"):
        raise HTTPException(400, "Неверный способ оплаты")

    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)
        try:
            billing = BillingService(session)
        except ValueError as e:
            raise HTTPException(503, str(e))

        try:
            if method == "platega":
                amount = float(payload.amount)
                pl_type = (payload.platega_type or "card").lower().strip()
                if pl_type not in ("card", "sbp"):
                    raise HTTPException(400, "Выберите карту или СБП")

                payment_method = PLATEGA_METHOD_CARD if pl_type == "card" else PLATEGA_METHOD_SBP

                payment = await billing.create_platega_payment(
                    user_id=user.id,
                    amount=amount,
                    payment_method=payment_method,
                    description=f"Пополнение баланса на {amount} RUB",
                    return_url="https://t.me/LunetVPNBot",
                    failed_url="https://t.me/LunetVPNBot",
                )

                payment_url = (
                    payment.get("redirect")
                    or payment.get("payformSuccessUrl")
                    or payment.get("payment_url")
                )
                provider_id = str(payment.get("id") or payment.get("transactionId") or "")

                return {
                    "ok": True,
                    "method": "platega",
                    "platega_type": pl_type,
                    "payment_url": payment_url,
                    "provider_id": provider_id,
                    "status": payment.get("status"),
                }

            if method == "pally":
                amount = float(payload.amount)
                payment = await billing.create_pally_payment(
                    user_id=user.id,
                    amount=amount,
                    description=f"Пополнение баланса на {amount} RUB",
                    return_url="https://t.me/LunetVPNBot",
                    failed_url="https://t.me/LunetVPNBot",
                )

                payment_url = (
                    payment.get("payment_url")
                    or payment.get("pay_url")
                    or payment.get("url")
                    or payment.get("link")
                    or payment.get("redirect")
                )
                provider_id = str(payment.get("id") or payment.get("bill_id") or "")

                return {
                    "ok": True,
                    "method": "pally",
                    "payment_url": payment_url,
                    "provider_id": provider_id,
                    "status": payment.get("status"),
                }

            invoice = await billing.create_crypto_invoice(
                user_id=user.id,
                amount_rub=int(payload.amount),
                asset=(payload.asset or "USDT"),
                description=f"Пополнение баланса на {payload.amount} RUB",
                expires_in=get_business_int("CRYPTO_INVOICE_EXPIRES_IN_SEC"),
            )

            payment_url = (
                invoice.get("pay_url")
                or invoice.get("bot_invoice_url")
                or invoice.get("mini_app_invoice_url")
                or invoice.get("web_app_invoice_url")
                or invoice.get("url")
            )
            invoice_id = invoice.get("invoice_id")

            return {
                "ok": True,
                "method": "crypto",
                "payment_url": payment_url,
                "provider_id": str(invoice_id) if invoice_id is not None else None,
                "status": invoice.get("status"),
                "asset": payload.asset or "USDT",
            }

        except HTTPException:
            raise
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()


@router.post("/balance/check")
async def mini_balance_check(payload: BalanceCheckPayload):
    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        billing = BillingService(session)
        tx_service = TransactionService(session)
        user_service = UserService(session)

        provider_id = (payload.provider_id or "").strip() or None

        if provider_id:
            method = (payload.method or "platega").lower().strip()
            if method not in ("platega", "crypto", "pally"):
                raise HTTPException(400, "method must be 'platega', 'crypto' or 'pally'")
            checked = 1
            candidates: list[tuple[str, str]] = [(method, provider_id)]
        else:
            recent_txs = await tx_service.list_recent_unpaid(
                user_id=user.id,
                limit=3,
                payment_systems={"platega", "pally", "cryptobot"},
            )
            if not recent_txs:
                return {
                    "ok": False,
                    "reason": "no_pending",
                    "checked": 0,
                    "message": "Нет незавершенных платежей",
                }
            candidates = [
                (_public_payment_method(tx.payment_system), tx.transaction_id)
                for tx in recent_txs
            ]
            checked = len(candidates)

        last_tx = None
        try:
            for method, provider_id in candidates:
                try:
                    await _confirm_transaction_by_method(billing, method, provider_id)
                except PaymentNotConfirmed:
                    try:
                        last_tx = await tx_service.get_by_provider_id(provider_id)
                    except TransactionNotFound:
                        last_tx = None
                    continue

                tx = await tx_service.get_by_provider_id(provider_id)
                fresh_user = await user_service.get_by_id(user.id)

                return {
                    "ok": True,
                    "confirmed": True,
                    "checked": checked,
                    "method": method,
                    "transaction": {
                        "id": tx.id,
                        "provider_id": tx.transaction_id,
                        "amount": int(tx.amount) if tx.amount is not None else None,
                        "paid": True,
                        "status_raw": "CONFIRMED",
                    },
                    "balance": fresh_user.balance,
                }
        except TransactionNotFound:
            return {
                "ok": False,
                "reason": "tx_not_found",
                "checked": checked,
                "message": "Transaction not found",
            }
        except Exception as e:
            raise _map_service_error(e)
        finally:
            await billing.close_clients()

        fresh_user = await user_service.get_by_id(user.id)
        if not last_tx:
            return {
                "ok": False,
                "reason": "tx_not_found",
                "checked": checked,
                "message": "Transaction not found",
            }

        return {
            "ok": True,
            "confirmed": False,
            "checked": checked,
            "method": _public_payment_method(last_tx.payment_system),
            "transaction": {
                "id": last_tx.id,
                "provider_id": last_tx.transaction_id,
                "amount": int(last_tx.amount) if last_tx.amount is not None else None,
                "paid": last_tx.paid,
                "status_raw": "NOT_CONFIRMED",
            },
            "balance": fresh_user.balance,
        }

