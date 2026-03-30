from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_UP

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger_config import logger
from backend.repositories.user_repository import UserRepository
from backend.repositories.transaction_repository import TransactionRepository

from backend.payments.platega import PlategaPaymentAPI
from backend.payments.cryptobot import CryptoPayAPI, CurrencyType
from backend.payments.pally import PallyPaymentAPI

from backend.services.subscription_service import SubscriptionService
from backend.services.exceptions import (
    UserNotFound,
    TransactionNotFound,
    InsufficientBalance,
    PaymentNotConfirmed,
    SubscriptionNotFound,
    TooEarlyToRenew,
)

USDT_RATE = Decimal("79")
TRAFFIC_PRICE_PER_GB_RUB = Decimal("0.5")
MIN_TRAFFIC_PURCHASE_GB = 5


class BillingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.tx_repo = TransactionRepository(session)
        self.sub_service = SubscriptionService(session)

        self.platega = PlategaPaymentAPI()
        self.crypto = CryptoPayAPI()
        self.pally: PallyPaymentAPI | None = None

    def _get_pally(self) -> PallyPaymentAPI:
        if self.pally is None:
            self.pally = PallyPaymentAPI()
        return self.pally

    @staticmethod
    def _extract_pally_id(payload: dict) -> str | None:
        for key in ("id", "bill_id", "billId", "invoice_id", "order_id"):
            value = payload.get(key)
            if value:
                return str(value)

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("id", "bill_id", "billId", "invoice_id", "order_id"):
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

        if payload.get("paid") is True or payload.get("is_paid") is True or payload.get("success") is True:
            return True
        if nested.get("paid") is True or nested.get("is_paid") is True or nested.get("success") is True:
            return True

        status = (
            payload.get("status")
            or payload.get("bill_status")
            or payload.get("state")
            or payload.get("payment_status")
            or nested.get("status")
            or nested.get("bill_status")
            or nested.get("state")
            or nested.get("payment_status")
            or ""
        )
        status_str = str(status).lower().strip()
        if status_str in {"paid", "SUCCESS"}:
            return True
        if status_str.isdigit() and int(status_str) == 1:
            return True
        return False

    async def create_platega_payment(
        self,
        user_id: int,
        amount: float,
        payment_method: int = 2,
        description: str | None = None,
        return_url: str | None = None,
        failed_url: str | None = None,
    ) -> dict:
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

        await self.session.commit()
        logger.info(
            "[biz][billing] platega_confirmed provider_id=%s user_id=%s amount=%s",
            provider_transaction_id,
            tx.user_id,
            tx.amount,
        )
        return tx

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
        expires_in: int | None = 900,
    ) -> dict:
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
            expires_in=expires_in,
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

        await self.session.commit()
        logger.info(
            "[biz][billing] crypto_confirmed invoice_id=%s user_id=%s amount=%s",
            invoice_id,
            tx.user_id,
            tx.amount,
        )
        return tx

    async def create_pally_payment(
        self,
        user_id: int,
        amount: float,
        description: str | None = None,
        return_url: str | None = None,
        failed_url: str | None = None,
        ttl: int = 600,
    ) -> dict:
        logger.info(
            "[biz][billing] pally_create_requested user_id=%s amount=%s ttl=%s",
            user_id,
            amount,
            ttl,
        )
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            logger.warning("[biz][billing] pally_create_user_not_found user_id=%s", user_id)
            raise UserNotFound(f"User with id:{user_id} not found")

        payload = f"PALLY-{user.id}-{int(datetime.now().timestamp())}"

        pally = self._get_pally()
        payment = await pally.create_invoice(
            amount=amount,
            order_id=payload,
            description=description or f"Top up {amount} RUB",
            success_url=return_url,
            fail_url=failed_url,
            ttl=ttl,
        )

        if payment.get("error"):
            logger.error(
                "[biz][billing] pally_create_api_error user_id=%s error=%s",
                user_id,
                payment.get("error"),
            )
            raise ValueError(f"PALLY API error: {payment.get('error')}")

        provider_id = self._extract_pally_id(payment)
        if not provider_id:
            logger.error("[biz][billing] pally_create_missing_provider_id user_id=%s", user_id)
            raise ValueError(f"PALLY API did not return bill id: {payment}")

        payment_url = self._extract_pally_url(payment)
        if payment_url and "payment_url" not in payment:
            payment["payment_url"] = payment_url
        payment["id"] = provider_id

        await self.tx_repo.create(
            user_id=user_id,
            provider_transaction_id=str(provider_id),
            payment_system="PALLY",
            amount=Decimal(amount),
            created_at=datetime.now(timezone.utc),
            paid=False,
            paid_at=None,
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] pally_created user_id=%s provider_id=%s amount=%s",
            user_id,
            provider_id,
            amount,
        )
        return payment

    async def confirm_pally_payment(self, provider_transaction_id: str):
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
        plan = await self.sub_service.get_plan(plan_id)

        now = datetime.now(timezone.utc)
        try:
            current_sub = await self.sub_service.get_active_subscription(user_id)
            end = current_sub.current_period_end
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if end and end > now and (end - now) > timedelta(days=3):
                logger.warning(
                    "[biz][billing] buy_subscription_too_early user_id=%s plan_id=%s seconds_left=%s",
                    user_id,
                    plan_id,
                    int((end - now).total_seconds()),
                )
                raise TooEarlyToRenew(
                    "Subscription can ony be renewed within 3 days before expiration"
                )
        except SubscriptionNotFound:
            pass

        await self.charge_balance(user_id=user_id, amount=plan.price)

        sub = await self.sub_service.activate_subscription(
            user_id=user_id,
            plan_id=plan_id,
            auto_renew=auto_renew,
        )

        await self.session.commit()
        logger.info(
            "[biz][billing] buy_subscription_completed user_id=%s subscription_id=%s plan_id=%s charged=%s",
            user_id,
            sub.id,
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
        if gb < MIN_TRAFFIC_PURCHASE_GB:
            raise ValueError(f"Minimum traffic purchase is {MIN_TRAFFIC_PURCHASE_GB} GB")

        price = (Decimal(gb) * TRAFFIC_PRICE_PER_GB_RUB).to_integral_value(rounding=ROUND_UP)

        await self.charge_balance(user_id=user_id, amount=price)

        sub = await self.sub_service.add_traffic(user_id=user_id, gb=Decimal(gb))

        await self.session.commit()
        logger.info(
            "[biz][billing] buy_traffic_completed user_id=%s subscription_id=%s gb=%s charged=%s",
            user_id,
            sub.id,
            gb,
            int(price),
        )
        return sub, int(price)
