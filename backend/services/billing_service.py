from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_UP
from html import escape

from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.core.business_config import get_business_decimal, get_business_int
from backend.core.telegram_notify import send_telegram_message_safe
from backend.repositories.user_repository import UserRepository
from backend.repositories.transaction_repository import TransactionRepository

from backend.payments.platega import PlategaPaymentAPI
from backend.payments.cryptobot import CryptoPayAPI, CurrencyType
from backend.payments.pally import PallyPaymentAPI

from backend.services.subscription_service import SubscriptionService
from backend.services.payment_method_service import get_payment_method_config
from backend.services.remnawave_service import RemnaWaveService
from backend.services.activity_service import ActivityService
from backend.services.exceptions import (
    BannedUser,
    UserNotFound,
    TransactionNotFound,
    InsufficientBalance,
    PaymentNotConfirmed,
    SubscriptionNotFound,
    TooEarlyToRenew,
    PurchaseInProgress,
)

USDT_RATE = Decimal("79")


class BillingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.tx_repo = TransactionRepository(session)
        self.sub_service = SubscriptionService(session)
        self.remnawave_service = RemnaWaveService(session)
        self.activity_service = ActivityService(session)

        self.platega: PlategaPaymentAPI | None = None
        self.crypto: CryptoPayAPI | None = None
        self.pally: PallyPaymentAPI | None = None
        self._payment_config_signature: tuple | None = None

    async def _ensure_payment_clients(self) -> None:
        """Apply admin-managed provider settings before making a provider request."""
        crypto = await get_payment_method_config(self.session, "cryptobot")
        pally = await get_payment_method_config(self.session, "pally")
        platega = await get_payment_method_config(self.session, "platega")
        signature = tuple(
            (method, key, value)
            for method, config in (("cryptobot", crypto), ("pally", pally), ("platega", platega))
            for key, value in sorted(config.items())
        )
        if signature == self._payment_config_signature:
            return
        self.platega = (
            PlategaPaymentAPI(merchant_id=platega["merchant_id"], secret=platega["secret"])
            if platega.get("merchant_id") and platega.get("secret") else None
        )
        self.crypto = CryptoPayAPI(api_token=crypto["api_token"]) if crypto.get("api_token") else None
        self.pally = (
            PallyPaymentAPI(
                api_token=pally["api_token"], shop_id=pally["shop_id"],
                success_url=pally.get("success_url"), fail_url=pally.get("fail_url")
            ) if pally.get("api_token") and pally.get("shop_id") else None
        )
        self._payment_config_signature = signature

    def _get_pally(self) -> PallyPaymentAPI:
        if self.pally is None:
            self.pally = PallyPaymentAPI()
        return self.pally

    @staticmethod
    def _extract_pally_id(payload: dict) -> str | None:
        for key in ("id", "bill_id", "billId", "invoice_id"):
            value = payload.get(key)
            if value:
                return str(value)

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("id", "bill_id", "billId", "invoice_id"):
                value = data.get(key)
                if value:
                    return str(value)
        return None

    @staticmethod
    def _extract_pally_url(payload: dict) -> str | None:
        for key in ("payment_url", "pay_url", "url", "link", "link_page_url", "redirect", "payformSuccessUrl"):
            value = payload.get(key)
            if value:
                return str(value)

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("payment_url", "pay_url", "url", "link", "link_page_url", "redirect"):
                value = data.get(key)
                if value:
                    return str(value)
        return None

    @staticmethod
    def _is_pally_paid(payload: dict) -> bool:
        nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        status = (
            nested.get("status")
            or nested.get("state")
            or payload.get("status")
            or payload.get("state")
            or ""
        )
        return str(status).strip().upper() == "SUCCESS"

    async def create_platega_payment(
        self,
        user_id: int,
        amount: float,
        payment_method: int = 2,
        description: str | None = None,
        return_url: str | None = None,
        failed_url: str | None = None,
    ) -> dict:
        await self._ensure_payment_clients()
        if self.platega is None:
            raise ValueError("Platega is not configured in the admin panel")
        logger.info(
            "[biz][billing] platega_create_requested user_id=%s amount=%s payment_method=%s",
            user_id,
            amount,
            payment_method,
        )
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("[biz][billing] platega_create_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")

        payload = f"TPU-{user.id}-{int(datetime.now().timestamp())}"

        payment = await self.platega.create_payment(
            amount=amount,
            payment_method=payment_method, 
            description=description,
            payload=payload,
            return_url=return_url,
            failed_url=failed_url,
        )

        await self.tx_repo.create(
            user_id=user_id,
            provider_transaction_id=str(payment.get("id")),
            payment_system="PLATEGA",
            amount=Decimal(amount),
            created_at=datetime.now(timezone.utc),
            paid=False,
            paid_at=None,
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] platega_created user_id=%s provider_id=%s amount=%s",
            user_id,
            payment.get("id"),
            amount,
        )

        return payment

    async def confirm_platega_payment(self, provider_transaction_id: str):
        await self._ensure_payment_clients()
        if self.platega is None:
            raise ValueError("Platega is not configured in the admin panel")
        logger.info(
            "[biz][billing] platega_confirm_requested provider_id=%s",
            provider_transaction_id,
        )
        tx = await self.tx_repo.get_by_provider_id_for_update(provider_transaction_id)
        if not tx:
            logger.warning(
                "[biz][billing] platega_confirm_tx_not_found provider_id=%s",
                provider_transaction_id,
            )
            raise TransactionNotFound("Transaction not found")

        if tx.paid:
            logger.info(
                "[biz][billing] platega_confirm_already_paid provider_id=%s user_id=%s",
                provider_transaction_id,
                tx.user_id,
            )
            return tx

        status = await self.platega.get_status(provider_transaction_id)
        if status.get("status") != "CONFIRMED":
            logger.warning(
                "[biz][billing] platega_not_confirmed provider_id=%s status=%s",
                provider_transaction_id,
                status.get("status"),
            )
            raise PaymentNotConfirmed("Payment not confirmed")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount)
        await self.tx_repo.mark_paid(
            provider_transaction_id=provider_transaction_id,
            paid_at=datetime.now(timezone.utc),
        )
        await self.activity_service.log_user_event(
            user_id=tx.user_id,
            category="billing",
            action="payment_confirmed",
            source="platega",
            amount=int(tx.amount or 0),
            transaction_id_ref=tx.id,
            note=f"Подтвержден платеж {provider_transaction_id}",
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] platega_confirmed provider_id=%s user_id=%s amount=%s",
            provider_transaction_id,
            tx.user_id,
            tx.amount,
        )
        return tx

    @staticmethod
    def verify_platega_webhook_headers(*, merchant_id: str | None, secret: str | None) -> bool:
        expected_merchant_id = (settings.PLATEGA_MERCHANT_ID or "").strip()
        expected_secret = (settings.PLATEGA_SECRET or "").strip()
        if not expected_merchant_id or not expected_secret:
            return False
        return (
            hmac.compare_digest(str(merchant_id or "").strip(), expected_merchant_id)
            and hmac.compare_digest(str(secret or "").strip(), expected_secret)
        )

    async def confirm_platega_webhook(
        self,
        *,
        provider_transaction_id: str,
        amount: Decimal | int | float | str,
        currency: str,
        status: str,
        payload: str | None = None,
        payment_method: int | None = None,
    ) -> tuple[object, bool]:
        normalized_status = str(status or "").strip().upper()
        logger.info(
            "[biz][billing] platega_webhook_received provider_id=%s status=%s amount=%s currency=%s payment_method=%s payload=%s",
            provider_transaction_id,
            normalized_status,
            amount,
            currency,
            payment_method,
            payload,
        )
        tx = await self.tx_repo.get_by_provider_id_for_update(str(provider_transaction_id))
        if not tx:
            logger.warning("[biz][billing] platega_webhook_tx_not_found provider_id=%s", provider_transaction_id)
            raise TransactionNotFound("Transaction not found")

        if tx.paid:
            logger.info(
                "[biz][billing] platega_webhook_already_paid provider_id=%s user_id=%s",
                provider_transaction_id,
                tx.user_id,
            )
            return tx, False

        if normalized_status != "CONFIRMED":
            logger.warning(
                "[biz][billing] platega_webhook_not_confirmed provider_id=%s user_id=%s status=%s",
                provider_transaction_id,
                tx.user_id,
                normalized_status,
            )
            raise PaymentNotConfirmed("Payment not confirmed")

        if str(currency or "").strip().upper() != "RUB":
            logger.warning(
                "[biz][billing] platega_webhook_bad_currency provider_id=%s user_id=%s currency=%s",
                provider_transaction_id,
                tx.user_id,
                currency,
            )
            raise PaymentNotConfirmed("Payment currency mismatch")

        try:
            paid_amount = Decimal(str(amount))
        except Exception:
            paid_amount = Decimal(0)
        expected_amount = Decimal(tx.amount or 0)
        if paid_amount < expected_amount:
            logger.warning(
                "[biz][billing] platega_webhook_underpaid provider_id=%s user_id=%s paid=%s expected=%s",
                provider_transaction_id,
                tx.user_id,
                paid_amount,
                expected_amount,
            )
            raise PaymentNotConfirmed("Payment underpaid")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount)
        await self.tx_repo.mark_paid(
            provider_transaction_id=str(provider_transaction_id),
            paid_at=datetime.now(timezone.utc),
        )
        await self.activity_service.log_user_event(
            user_id=tx.user_id,
            category="billing",
            action="payment_confirmed",
            source="platega_webhook",
            amount=int(tx.amount or 0),
            transaction_id_ref=tx.id,
            note=f"Подтвержден Platega callback {provider_transaction_id}",
        )
        await self.session.commit()
        logger.info(
            "[biz][billing] platega_webhook_confirmed provider_id=%s user_id=%s amount=%s",
            provider_transaction_id,
            tx.user_id,
            tx.amount,
        )
        return tx, True

    async def close_clients(self) -> None:
        try:
            await self.platega.close()
        except Exception:
            pass

        try:
            await self.crypto.close()
        except Exception:
            pass

        try:
            if self.pally:
                await self.pally.close()
        except Exception:
            pass

    async def create_crypto_invoice(
        self,
        user_id: int,
        amount_rub: int,
        *,
        asset: str = "USDT",
        description: str | None = None,
        expires_in: int | None = None,
    ) -> dict:
        await self._ensure_payment_clients()
        if self.crypto is None:
            raise ValueError("CryptoBot is not configured in the admin panel")
        logger.info(
            "[biz][billing] crypto_create_requested user_id=%s amount_rub=%s asset=%s",
            user_id,
            amount_rub,
            asset,
        )
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("[biz][billing] crypto_create_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")

        amount_crypto = (Decimal(amount_rub) / USDT_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_UP
        )

        payload = f"TPU-{user.id}-{int(datetime.now().timestamp())}"

        invoice = await self.crypto.create_invoice(
            amount=float(amount_crypto),
            currency_type=CurrencyType.CRYPTO,
            asset=asset,
            description=description or f"Top up {amount_rub} RUB",
            payload=payload,
            expires_in=expires_in or get_business_int("CRYPTO_INVOICE_EXPIRES_IN_SEC"),
        )

        await self.tx_repo.create(
            user_id=user_id,
            provider_transaction_id=str(invoice["invoice_id"]),
            payment_system="CRYPTOBOT",
            amount=Decimal(amount_rub), 
            created_at=datetime.now(timezone.utc),
            paid=False,
            paid_at=None,
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] crypto_created user_id=%s invoice_id=%s amount_rub=%s amount_crypto=%s",
            user_id,
            invoice.get("invoice_id"),
            amount_rub,
            amount_crypto,
        )
        return invoice

    async def confirm_crypto_payment(self, invoice_id: int):
        await self._ensure_payment_clients()
        if self.crypto is None:
            raise ValueError("CryptoBot is not configured in the admin panel")
        logger.info("[biz][billing] crypto_confirm_requested invoice_id=%s", invoice_id)
        tx = await self.tx_repo.get_by_provider_id_for_update(str(invoice_id))
        if not tx:
            logger.warning("[biz][billing] crypto_confirm_tx_not_found invoice_id=%s", invoice_id)
            raise TransactionNotFound("Transaction not found")

        if tx.paid:
            logger.info(
                "[biz][billing] crypto_confirm_already_paid invoice_id=%s user_id=%s",
                invoice_id,
                tx.user_id,
            )
            return tx

        invoice = await self.crypto.get_invoice_status(invoice_id)
        if invoice.get("status") != "paid":
            logger.warning(
                "[biz][billing] crypto_not_paid invoice_id=%s status=%s",
                invoice_id,
                invoice.get("status"),
            )
            raise PaymentNotConfirmed("Invoice not paid")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount) 
        await self.tx_repo.mark_paid(
            provider_transaction_id=str(invoice_id),
            paid_at=datetime.now(timezone.utc),
        )
        await self.activity_service.log_user_event(
            user_id=tx.user_id,
            category="billing",
            action="payment_confirmed",
            source="cryptobot",
            amount=int(tx.amount or 0),
            transaction_id_ref=tx.id,
            note=f"Подтвержден платеж {invoice_id}",
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] crypto_confirmed invoice_id=%s user_id=%s amount=%s",
            invoice_id,
            tx.user_id,
            tx.amount,
        )
        return tx

    @staticmethod
    def verify_crypto_webhook_signature(*, body: bytes, signature: str | None) -> bool:
        token = (settings.CRYPTOBOT_SECRET or "").strip()
        if not token or not signature:
            return False
        secret = hashlib.sha256(token.encode("utf-8")).digest()
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected.lower(), str(signature).strip().lower())

    async def confirm_crypto_webhook(
        self,
        *,
        invoice_id: int,
        status: str,
        update_type: str,
    ) -> tuple[object, bool]:
        normalized_status = str(status or "").strip().lower()
        normalized_update_type = str(update_type or "").strip()
        logger.info(
            "[biz][billing] crypto_webhook_received invoice_id=%s update_type=%s status=%s",
            invoice_id,
            normalized_update_type,
            normalized_status,
        )

        tx = await self.tx_repo.get_by_provider_id_for_update(str(invoice_id))
        if not tx:
            logger.warning("[biz][billing] crypto_webhook_tx_not_found invoice_id=%s", invoice_id)
            raise TransactionNotFound("Transaction not found")

        if tx.paid:
            logger.info(
                "[biz][billing] crypto_webhook_already_paid invoice_id=%s user_id=%s",
                invoice_id,
                tx.user_id,
            )
            return tx, False

        if normalized_update_type != "invoice_paid" or normalized_status != "paid":
            logger.warning(
                "[biz][billing] crypto_webhook_not_paid invoice_id=%s user_id=%s update_type=%s status=%s",
                invoice_id,
                tx.user_id,
                normalized_update_type,
                normalized_status,
            )
            raise PaymentNotConfirmed("Invoice not paid")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount)
        await self.tx_repo.mark_paid(
            provider_transaction_id=str(invoice_id),
            paid_at=datetime.now(timezone.utc),
        )
        await self.activity_service.log_user_event(
            user_id=tx.user_id,
            category="billing",
            action="payment_confirmed",
            source="cryptobot_webhook",
            amount=int(tx.amount or 0),
            transaction_id_ref=tx.id,
            note=f"Подтвержден CryptoBot webhook {invoice_id}",
        )
        await self.session.commit()
        logger.info(
            "[biz][billing] crypto_webhook_confirmed invoice_id=%s user_id=%s amount=%s",
            invoice_id,
            tx.user_id,
            tx.amount,
        )
        return tx, True

    async def create_pally_payment(
        self,
        user_id: int,
        amount: float,
        description: str | None = None,
        return_url: str | None = None,
        failed_url: str | None = None,
        ttl: int | None = None,
    ) -> dict:
        await self._ensure_payment_clients()
        if self.pally is None:
            raise ValueError("Pally is not configured in the admin panel")
        logger.info(
            "[biz][billing] pally_create_requested user_id=%s amount=%s ttl=%s",
            user_id,
            amount,
            ttl or get_business_int("PALLY_INVOICE_TTL_SEC"),
        )
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("[biz][billing] pally_create_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")

        # The payment provider echoes this value in InvId.  A seconds-only
        # timestamp can collide when a user opens two invoices quickly.
        payload = f"PALLY-{user.id}-{uuid.uuid4().hex[:16]}"

        pally = self._get_pally()
        payment = await pally.create_invoice(
            amount=amount,
            order_id=payload,
            description=description or f"Top up {amount} RUB",
            # Redirect URLs are controlled by the Pally settings in the
            # admin panel; request-specific defaults must not override them.
            success_url=None,
            fail_url=None,
            ttl=ttl or get_business_int("PALLY_INVOICE_TTL_SEC"),
        )

        if payment.get("error"):
            http_status = payment.get("http_status")
            provider_error = payment.get("error")
            provider_message = payment.get("message") or payment.get("detail")
            provider_response = payment.get("response")
            payload_preview = str(payment)[:2000]

            if int(http_status or 0) == 403:
                logger.error(
                    "[biz][billing] pally_create_http_403 user_id=%s status=%s error=%s message=%s response=%s payload=%s",
                    user_id,
                    http_status,
                    provider_error,
                    provider_message,
                    provider_response,
                    payload_preview,
                )
            logger.error(
                "[biz][billing] pally_create_api_error user_id=%s status=%s error=%s message=%s response=%s payload=%s",
                user_id,
                http_status,
                provider_error,
                provider_message,
                provider_response,
                payload_preview,
            )
            raise ValueError(f"PALLY API error: {payment.get('error')}")

        provider_bill_id = self._extract_pally_id(payment)
        if not provider_bill_id:
            logger.error("[biz][billing] pally_create_missing_provider_id user_id=%s", user_id)
            raise ValueError(f"PALLY API did not return bill id: {payment}")

        payment_url = self._extract_pally_url(payment)
        if payment_url and "payment_url" not in payment:
            payment["payment_url"] = payment_url
        # Keep the payment-system bill ID as the public/provider transaction
        # ID, just like the Platega and CryptoBot integrations do.  The
        # merchant order ID is only used to correlate legacy Pally postbacks.
        payment["id"] = provider_bill_id
        payment["order_id"] = payload
        payment["bill_id"] = provider_bill_id

        await self.tx_repo.create(
            user_id=user_id,
            provider_transaction_id=provider_bill_id,
            payment_system="PALLY",
            amount=Decimal(amount),
            created_at=datetime.now(timezone.utc),
            paid=False,
            paid_at=None,
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] pally_created user_id=%s inv_id=%s provider_id=%s amount=%s",
            user_id,
            payload,
            provider_bill_id,
            amount,
        )
        return payment

    @staticmethod
    def verify_pally_postback_signature(*, inv_id: str, out_sum: str, signature: str) -> bool:
        token = (settings.PALLY_API_TOKEN or "").strip()
        if not token or not signature:
            return False
        expected = hashlib.md5(f"{out_sum}:{inv_id}:{token}".encode("utf-8")).hexdigest().upper()
        return hmac.compare_digest(expected, str(signature).strip().upper())

    async def confirm_pally_postback(
        self,
        *,
        inv_id: str,
        out_sum: str,
        status: str,
        trs_id: str | None = None,
    ) -> tuple[object, bool]:
        normalized_status = str(status or "").strip().upper()
        logger.info(
            "[biz][billing] pally_postback_received inv_id=%s trs_id=%s status=%s out_sum=%s",
            inv_id,
            trs_id,
            normalized_status,
            out_sum,
        )
        # Pally's transaction ID is sent as TrsId. InvId is only the merchant
        # order ID and must never be used as our transaction ID.
        provider_id = str(trs_id or "").strip()
        tx = await self.tx_repo.get_by_provider_id_for_update(provider_id) if provider_id else None
        if not tx:
            logger.warning("[biz][billing] pally_postback_tx_not_found inv_id=%s trs_id=%s", inv_id, trs_id)
            raise TransactionNotFound("Transaction not found")

        paid_before = bool(tx.paid)
        if paid_before:
            logger.info("[biz][billing] pally_postback_already_paid inv_id=%s user_id=%s", inv_id, tx.user_id)
            return tx, False

        if normalized_status != "SUCCESS":
            logger.warning(
                "[biz][billing] pally_postback_not_success inv_id=%s user_id=%s status=%s",
                inv_id,
                tx.user_id,
                normalized_status,
            )
            raise PaymentNotConfirmed("Payment not confirmed")

        try:
            paid_amount = Decimal(str(out_sum))
        except Exception:
            paid_amount = Decimal(0)
        expected_amount = Decimal(tx.amount or 0)
        if paid_amount < expected_amount:
            logger.warning(
                "[biz][billing] pally_postback_underpaid inv_id=%s user_id=%s paid=%s expected=%s",
                inv_id,
                tx.user_id,
                paid_amount,
                expected_amount,
            )
            raise PaymentNotConfirmed("Payment underpaid")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount)
        await self.tx_repo.mark_paid(
            provider_transaction_id=provider_id,
            paid_at=datetime.now(timezone.utc),
        )
        await self.activity_service.log_user_event(
            user_id=tx.user_id,
            category="billing",
            action="payment_confirmed",
            source="pally_webhook",
            amount=int(tx.amount or 0),
            transaction_id_ref=tx.id,
            note=f"Подтвержден Pally postback {trs_id or inv_id}",
        )
        await self.session.commit()
        logger.info(
            "[biz][billing] pally_postback_confirmed inv_id=%s trs_id=%s user_id=%s amount=%s",
            inv_id,
            trs_id,
            tx.user_id,
            tx.amount,
        )
        return tx, True

    async def confirm_pally_payment(self, provider_transaction_id: str):
        await self._ensure_payment_clients()
        if self.pally is None:
            raise ValueError("Pally is not configured in the admin panel")
        logger.info(
            "[biz][billing] pally_confirm_requested provider_id=%s",
            provider_transaction_id,
        )
        tx = await self.tx_repo.get_by_provider_id_for_update(provider_transaction_id)
        if not tx:
            logger.warning(
                "[biz][billing] pally_confirm_tx_not_found provider_id=%s",
                provider_transaction_id,
            )
            raise TransactionNotFound("Transaction not found")

        if tx.paid:
            logger.info(
                "[biz][billing] pally_confirm_already_paid provider_id=%s user_id=%s",
                provider_transaction_id,
                tx.user_id,
            )
            return tx

        pally = self._get_pally()
        status = await pally.get_status(provider_transaction_id)
        if not self._is_pally_paid(status):
            logger.warning(
                "[biz][billing] pally_not_paid provider_id=%s status=%s",
                provider_transaction_id,
                status,
            )
            raise PaymentNotConfirmed("Payment not confirmed")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount)
        await self.tx_repo.mark_paid(
            provider_transaction_id=provider_transaction_id,
            paid_at=datetime.now(timezone.utc),
        )
        await self.activity_service.log_user_event(
            user_id=tx.user_id,
            category="billing",
            action="payment_confirmed",
            source="pally",
            amount=int(tx.amount or 0),
            transaction_id_ref=tx.id,
            note=f"Подтвержден платеж {provider_transaction_id}",
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] pally_confirmed provider_id=%s user_id=%s amount=%s",
            provider_transaction_id,
            tx.user_id,
            tx.amount,
        )
        return tx

    async def charge_balance(self, user_id: int, amount: Decimal):
        logger.info(
            "[biz][billing] charge_balance_requested user_id=%s amount=%s",
            user_id,
            amount,
        )
        user = await self.user_repo.get_by_id_for_update(user_id)
        if not user:
            logger.warning("[biz][billing] charge_balance_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")

        if user.balance < amount:
            logger.warning(
                "[biz][billing] charge_balance_insufficient user_id=%s balance=%s required=%s",
                user_id,
                user.balance,
                amount,
            )
            raise InsufficientBalance("Insufficient balance")

        await self.user_repo.sub_balance(user_id=user_id, amount=amount)
        logger.info(
            "[biz][billing] charge_balance_completed user_id=%s amount=%s",
            user_id,
            amount,
        )

    @staticmethod
    def _is_lock_not_available_error(exc: OperationalError) -> bool:
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
        if sqlstate == "55P03":
            return True

        text = str(orig or exc).lower()
        return "lock not available" in text or "database is locked" in text

    async def buy_subscription(
        self,
        user_id: int,
        plan_id: int,
        auto_renew: bool = True,
    ):
        logger.info(
            "[biz][billing] buy_subscription_requested user_id=%s plan_id=%s auto_renew=%s",
            user_id,
            plan_id,
            auto_renew,
        )

        try:
            user = await self.user_repo.get_by_id_for_update_nowait(user_id)
        except OperationalError as e:
            if self._is_lock_not_available_error(e):
                logger.info(
                    "[biz][billing] buy_subscription_locked user_id=%s plan_id=%s",
                    user_id,
                    plan_id,
                )
                raise PurchaseInProgress("Покупка уже обрабатывается. Подождите пару секунд.")
            raise

        if not user:
            logger.warning("[biz][billing] buy_subscription_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")
        if bool(getattr(user, "banned", False)):
            logger.warning("[biz][billing] buy_subscription_banned user_id=%s plan_id=%s", user_id, plan_id)
            raise BannedUser("User is banned")

        plan = await self.sub_service.get_public_plan(plan_id)

        now = datetime.now(timezone.utc)
        try:
            current_sub = await self.sub_service.get_active_subscription(user_id)
            end = current_sub.current_period_end
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            renewal_window_days = get_business_int("SUBSCRIPTION_RENEWAL_WINDOW_DAYS")
            if end and end > now and (end - now) > timedelta(days=renewal_window_days):
                logger.warning(
                    "[biz][billing] buy_subscription_too_early user_id=%s plan_id=%s seconds_left=%s",
                    user_id,
                    plan_id,
                    int((end - now).total_seconds()),
                )
                raise TooEarlyToRenew(
                    f"Subscription can only be renewed within {renewal_window_days} days before expiration"
                )
        except SubscriptionNotFound:
            pass

        await self.charge_balance(user_id=user_id, amount=plan.price)

        sub = await self.sub_service.activate_subscription(
            user_id=user_id,
            plan_id=plan_id,
            auto_renew=auto_renew,
        )
        subscription_id = sub.id
        # Make renewal bonus/topups visible to subsequent aggregate queries in this transaction.
        await self.session.flush()

        # Try syncing in Remnawave, but do not fail billing if panel is temporarily unreachable.
        try:
            sub_url = await self.remnawave_service.get_subscription_url(user=user, subscription=sub)
            if not sub_url:
                logger.warning(
                    "[biz][billing] remnawave_sync_empty_subscription_url user_id=%s subscription_id=%s plan_id=%s",
                    user_id,
                    subscription_id,
                    plan_id,
                )
        except Exception as e:
            await self.session.rollback()
            logger.exception(
                "[biz][billing] remnawave_sync_failed_non_blocking user_id=%s subscription_id=%s plan_id=%s: %s",
                user_id,
                subscription_id,
                plan_id,
                e,
            )

        try:
            await self.remnawave_service.sync_user_state(
                user=user,
                subscription=sub,
                status="ACTIVE",
            )
        except Exception as e:
            await self.session.rollback()
            logger.exception(
                "[biz][billing] remnawave_state_sync_failed_non_blocking user_id=%s subscription_id=%s plan_id=%s: %s",
                user_id,
                subscription_id,
                plan_id,
                e,
            )

        refreshed_sub = await self.sub_service.sub_repo.get_by_user_id(user_id)
        if refreshed_sub is not None:
            sub = refreshed_sub
            subscription_id = sub.id

        await self.session.commit()
        await self.activity_service.log_user_event(
            user_id=user_id,
            category="subscription",
            action="subscription_purchased",
            source="user",
            amount=int(plan.price or 0),
            subscription_id=subscription_id,
            note=f"Покупка/продление подписки plan_id={plan_id}",
        )
        await self.session.commit()
        logger.info(
            "[biz][billing] buy_subscription_completed user_id=%s subscription_id=%s plan_id=%s charged=%s",
            user_id,
            subscription_id,
            plan_id,
            plan.price,
        )
        return sub

    async def add_gb_to_subscription(self, user_id: int, gb: int):
        logger.info(
            "[biz][billing] buy_traffic_requested user_id=%s gb=%s",
            user_id,
            gb,
        )
        min_traffic_purchase_gb = get_business_int("MIN_TRAFFIC_PURCHASE_GB")
        if gb < min_traffic_purchase_gb:
            raise ValueError(f"Minimum traffic purchase is {min_traffic_purchase_gb} GB")

        price_per_gb = get_business_decimal("TRAFFIC_PRICE_PER_GB_RUB")
        price = (Decimal(gb) * price_per_gb).to_integral_value(rounding=ROUND_UP)
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        if bool(getattr(user, "banned", False)):
            logger.warning("[biz][billing] buy_traffic_banned user_id=%s gb=%s", user_id, gb)
            raise BannedUser("User is banned")

        await self.charge_balance(user_id=user_id, amount=price)

        sub = await self.sub_service.add_traffic(user_id=user_id, gb=Decimal(gb))
        # Ensure newly added topup row is visible for aggregate SUM in the same transaction.
        await self.session.flush()

        try:
            await self.remnawave_service.sync_user_state(
                user=user,
                subscription=sub,
                status="ACTIVE",
            )
        except Exception as e:
            logger.exception(
                "[biz][billing] remnawave_state_sync_failed_non_blocking user_id=%s subscription_id=%s gb=%s: %s",
                user_id,
                sub.id,
                gb,
                e,
            )

        await self.session.commit()
        await self.activity_service.log_user_event(
            user_id=user_id,
            category="traffic",
            action="traffic_purchased",
            source="user",
            amount=int(price),
            traffic_gb=gb,
            subscription_id=sub.id,
            note="Покупка дополнительного трафика",
        )
        await self.session.commit()
        logger.info(
            "[biz][billing] buy_traffic_completed user_id=%s subscription_id=%s gb=%s charged=%s",
            user_id,
            sub.id,
            gb,
            int(price),
        )
        return sub, int(price)

    async def add_device_slots_to_subscription(self, user_id: int, slots: int):
        logger.info("[biz][billing] buy_device_slots_requested user_id=%s slots=%s", user_id, slots)
        if slots <= 0:
            raise ValueError("Slots must be > 0")

        price_per_slot = get_business_decimal("DEVICE_SLOT_PRICE_RUB")
        price = (Decimal(slots) * price_per_slot).to_integral_value(rounding=ROUND_UP)
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")
        if bool(getattr(user, "banned", False)):
            raise BannedUser("User is banned")

        await self.charge_balance(user_id=user_id, amount=price)
        sub = await self.sub_service.add_device_slots(user_id=user_id, slots=slots)

        try:
            await self.remnawave_service.sync_user_state(user=user, subscription=sub, status="ACTIVE")
        except Exception as e:
            logger.exception(
                "[biz][billing] remnawave_device_slots_sync_failed_non_blocking user_id=%s subscription_id=%s slots=%s: %s",
                user_id,
                sub.id,
                slots,
                e,
            )

        await self.session.commit()
        await self.activity_service.log_user_event(
            user_id=user_id,
            category="subscription",
            action="device_slots_purchased",
            source="user",
            amount=int(price),
            subscription_id=sub.id,
            note=f"Докуплено устройств: {slots}",
        )
        await self.session.commit()
        return sub, int(price)

    async def gift_subscription(self, *, buyer_user_id: int, recipient_user_id: int, plan_id: int):
        logger.info(
            "[biz][billing] gift_subscription_requested buyer_user_id=%s recipient_user_id=%s plan_id=%s",
            buyer_user_id,
            recipient_user_id,
            plan_id,
        )
        buyer = await self.user_repo.get_by_id(buyer_user_id)
        recipient = await self.user_repo.get_by_id(recipient_user_id)
        if not buyer:
            raise UserNotFound(f"User with id:{buyer_user_id} not found")
        if not recipient:
            raise UserNotFound(f"User with id:{recipient_user_id} not found")
        if bool(getattr(buyer, "banned", False)) or bool(getattr(recipient, "banned", False)):
            raise BannedUser("User is banned")

        plan = await self.sub_service.get_public_plan(plan_id)
        await self.charge_balance(user_id=buyer_user_id, amount=plan.price)
        sub = await self.sub_service.activate_subscription(
            user_id=recipient_user_id,
            plan_id=plan_id,
            auto_renew=False,
            enforce_renewal_window=False,
        )

        try:
            await self.remnawave_service.sync_user_state(user=recipient, subscription=sub, status="ACTIVE")
        except Exception as e:
            logger.exception(
                "[biz][billing] remnawave_gift_sync_failed_non_blocking buyer_user_id=%s recipient_user_id=%s subscription_id=%s: %s",
                buyer_user_id,
                recipient_user_id,
                sub.id,
                e,
            )

        await self.session.commit()
        await self.activity_service.log_user_event(
            user_id=buyer_user_id,
            category="subscription",
            action="subscription_gift_sent",
            source="user",
            amount=int(plan.price or 0),
            subscription_id=sub.id,
            note=f"Подарок пользователю tg_id={recipient.tg_id}, plan_id={plan_id}",
        )
        await self.activity_service.log_user_event(
            user_id=recipient_user_id,
            category="subscription",
            action="subscription_gift_received",
            source="user",
            subscription_id=sub.id,
            note=f"Подарочная подписка от tg_id={buyer.tg_id}, plan_id={plan_id}",
        )
        await self.session.commit()

        buyer_name = f"@{buyer.username}" if getattr(buyer, "username", None) else f"ID {buyer.tg_id}"
        end_text = sub.current_period_end.strftime("%d.%m.%Y") if sub.current_period_end else "—"
        builder = InlineKeyboardBuilder()
        builder.button(
            text="Моя подписка",
            callback_data="vpn_subscription",
            icon_custom_emoji_id="6005570495603282482",
            style="primary",
        )
        builder.adjust(1)
        await send_telegram_message_safe(
            chat_id=int(recipient.tg_id),
            text=(
                "<b><tg-emoji emoji-id='5956148757899776734'>🎁</tg-emoji> Вам подарили подписку</b>\n\n"
                f"<blockquote><tg-emoji emoji-id='5967456680940671207'>🗃</tg-emoji> Тариф: <b>{escape(str(plan.name))}</b>\n"
                f"<tg-emoji emoji-id='5843799474362652262'>🔄</tg-emoji> Действует до: <b>{end_text}</b>\n"
                f"<tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Отправитель: <b>{escape(str(buyer_name))}</b></blockquote>\n\n"
                "Откройте раздел «Моя подписка», чтобы получить ссылку и подключить VPN."
            ),
            reply_markup=builder.as_markup(),
            log_prefix="[biz][billing][gift]",
        )
        return sub, int(plan.price or 0), recipient
