from fastapi import APIRouter

from ..common import *

router = APIRouter()


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
                provider_id = str(payment.get("id") or "")

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
                expires_in=900,
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


@router.post("/balance/check")
async def mini_balance_check(payload: BalanceCheckPayload):
    method = (payload.method or "platega").lower().strip()
    if method not in ("platega", "crypto", "pally"):
        raise HTTPException(400, "method must be 'platega', 'crypto' or 'pally'")

    tg_user = _get_tg_user(payload.initData)
    tg_id = tg_user["id"]

    async with async_session() as session:
        user = await _get_user_or_404(session, tg_id)

        billing = BillingService(session)
        tx_service = TransactionService(session)
        user_service = UserService(session)

        provider_id = (payload.provider_id or "").strip() or None

        if not provider_id:
            if method == "platega":
                payment_system = "platega"
            elif method == "pally":
                payment_system = "PALLY"
            else:
                payment_system = "cryptobot"
            tx = await tx_service.get_last_unpaid_by_system(
                user_id=user.id,
                payment_system=payment_system,
            )
            if not tx:
                return {"ok": False, "reason": "no_pending", "message": "��� ������������� ��������"}
            provider_id = tx.transaction_id

        try:
            if method == "platega":
                await billing.confirm_platega_payment(provider_id)
            elif method == "pally":
                await billing.confirm_pally_payment(provider_id)
            else:
                try:
                    invoice_id = int(provider_id)
                except ValueError:
                    raise HTTPException(400, "provider_id must be invoice_id (int) for crypto")
                await billing.confirm_crypto_payment(invoice_id)

        except PaymentNotConfirmed:
            try:
                tx = await tx_service.get_by_provider_id(provider_id)
            except TransactionNotFound:
                return {"ok": False, "reason": "tx_not_found", "message": "Transaction not found"}

            fresh_user = await user_service.get_by_id(user.id)
            return {
                "ok": True,
                "confirmed": False,
                "method": method,
                "transaction": {
                    "id": tx.id,
                    "provider_id": tx.transaction_id,
                    "amount": int(tx.amount) if tx.amount is not None else None,
                    "paid": tx.paid,
                    "status_raw": "NOT_CONFIRMED",
                },
                "balance": fresh_user.balance,
            }
        except TransactionNotFound:
            return {"ok": False, "reason": "tx_not_found", "message": "Transaction not found"}
        except Exception as e:
            raise _map_service_error(e)
        finally:
            try:
                await billing.platega.close()
            except Exception:
                pass
            try:
                if billing.pally:
                    await billing.pally.close()
            except Exception:
                pass
            try:
                await billing.crypto.close()
            except Exception:
                pass

        tx = await tx_service.get_by_provider_id(provider_id)
        fresh_user = await user_service.get_by_id(user.id)

        return {
            "ok": True,
            "confirmed": True,
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

