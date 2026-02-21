from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_UP

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.user_repository import UserRepository
from backend.repositories.transaction_repository import TransactionRepository

from backend.payments.platega import PlategaPaymentAPI
from backend.payments.cryptobot import CryptoPayAPI, CurrencyType

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


class BillingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.tx_repo = TransactionRepository(session)
        self.sub_service = SubscriptionService(session)

        self.platega = PlategaPaymentAPI()
        self.crypto = CryptoPayAPI()

    async def create_platega_payment(
        self,
        user_id: int,
        amount: float,
        payment_method: int = 2,
        description: str | None = None,
        return_url: str | None = None,
        failed_url: str | None = None,
    ) -> dict:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
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

        return payment

    async def confirm_platega_payment(self, provider_transaction_id: str):
        tx = await self.tx_repo.get_by_provider_id_for_update(provider_transaction_id)
        if not tx:
            raise TransactionNotFound("Transaction not found")

        if tx.paid:
            return tx

        status = await self.platega.get_status(provider_transaction_id)
        if status.get("status") != "CONFIRMED":
            raise PaymentNotConfirmed("Payment not confirmed")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount)
        await self.tx_repo.mark_paid(
            provider_transaction_id=provider_transaction_id,
            paid_at=datetime.now(timezone.utc),
        )

        await self.session.commit()
        return tx

    async def create_crypto_invoice(
        self,
        user_id: int,
        amount_rub: int,
        *,
        asset: str = "USDT",
        description: str | None = None,
        expires_in: int | None = 900,
    ) -> dict:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
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
        return invoice

    async def confirm_crypto_payment(self, invoice_id: int):
        tx = await self.tx_repo.get_by_provider_id_for_update(str(invoice_id))
        if not tx:
            raise TransactionNotFound("Transaction not found")

        if tx.paid:
            return tx

        invoice = await self.crypto.get_invoice_status(invoice_id)
        if invoice.get("status") != "paid":
            raise PaymentNotConfirmed("Invoice not paid")

        await self.user_repo.add_balance(user_id=tx.user_id, amount=tx.amount) 
        await self.tx_repo.mark_paid(
            provider_transaction_id=str(invoice_id),
            paid_at=datetime.now(timezone.utc),
        )

        await self.session.commit()
        return tx

    async def charge_balance(self, user_id: int, amount: Decimal):
        user = await self.user_repo.get_by_id_for_update(user_id)
        if not user:
            raise UserNotFound(f"User with id:{user_id} not found")

        if user.balance < amount:
            raise InsufficientBalance("Insufficient balance")

        await self.user_repo.sub_balance(user_id=user_id, amount=amount)

    async def buy_subscription(
        self,
        user_id: int,
        plan_id: int,
        auto_renew: bool = True,
    ):
        plan = await self.sub_service.get_plan(plan_id)

        now = datetime.now(timezone.utc)
        try:
            current_sub = await self.sub_service.get_active_subscription(user_id)
            end = current_sub.current_period_end
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if end and end > now and (end - now) > timedelta(days=3):
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
        return sub

    async def add_gb_to_subscription(self, user_id: int, gb: int):
        price = Decimal(gb) * Decimal(10)

        await self.charge_balance(user_id=user_id, amount=price)

        sub = await self.sub_service.add_traffic(user_id=user_id, gb=Decimal(gb))

        await self.session.commit()
        return sub
