from datetime import datetime
import enum

from sqlalchemy import (
    String,
    BigInteger,
    Boolean,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
    Numeric
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)
from decimal import Decimal

class Base(DeclarativeBase):
    pass


class Country(str, enum.Enum):
    RU_MOSCOW = "RU_MOSCOW"
    DE = "DE"


class KeyStatus(str, enum.Enum):
    active = "active"
    deleted = "deleted"


class SubStatus(str, enum.Enum):
    active = "active"
    past_due = "past_due"
    expired = "expired"
    canceled = "canceled"

class User(Base):
    __tablename__ = "vpn_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(32), nullable=True)

    referrer_id: Mapped[int | None] = mapped_column(
        ForeignKey("vpn_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    balance: Mapped[int] = mapped_column(default=0)
    email: Mapped[str | None] = mapped_column(nullable=True, unique=True)
    subscription_token: Mapped[str | None] = mapped_column(String(36), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    keys: Mapped[list["Key"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Server(Base):
    __tablename__ = "vpn_servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[Country] = mapped_column(String(64))

    inbound_tag: Mapped[str] = mapped_column(String(64))

    grpc_endpoint: Mapped[str] = mapped_column(String(128))

    public_host: Mapped[str] = mapped_column(String(255))

    port: Mapped[int] = mapped_column(default=443)
    sni: Mapped[str] = mapped_column(String(255), default="telegram.com")
    fp: Mapped[str] = mapped_column(String(32), default="chrome")
    pbk: Mapped[str] = mapped_column(String(128))  
    short_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    keys: Mapped[list["Key"]] = relationship(back_populates="server", cascade="all, delete-orphan")

class Key(Base):
    __tablename__ = "vpn_keys"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("vpn_users.id", ondelete="CASCADE"))
    server_id: Mapped[int] = mapped_column(ForeignKey("vpn_servers.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship(back_populates="keys")
    server: Mapped["Server"] = relationship(back_populates="keys")

    uuid: Mapped[str] = mapped_column(String(36), unique=True)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[KeyStatus] = mapped_column(Enum(KeyStatus), default=KeyStatus.active)

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

class SubscriptionPlan(Base):
    __tablename__ = "vpn_subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    price: Mapped[int] = mapped_column()
    period_days: Mapped[int] = mapped_column(default=30)
    gb_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=100)

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan", cascade="all, delete-orphan")

class Subscription(Base):
    __tablename__ = "vpn_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("vpn_users.id", ondelete="CASCADE"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("vpn_subscription_plans.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="subscriptions")

    gb_left: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=100)
    status: Mapped[SubStatus] = mapped_column(Enum(SubStatus), default=SubStatus.active)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)

    current_period_start: Mapped[datetime] = mapped_column(default=datetime.now)
    current_period_end: Mapped[datetime] = mapped_column(default=datetime.now)
    next_renewal_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

class Transaction(Base):
    __tablename__ = "vpn_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(255))
    amount: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    payment_system: Mapped[str] = mapped_column(String(32))
    order_id: Mapped[str] = mapped_column()

    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("vpn_users.id"))

    user: Mapped["User"] = relationship(back_populates="transactions")


class Promocode(Base):
    __tablename__ = "vpn_promocodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(default=0, nullable=False)
    usages: Mapped[int] = mapped_column(default=1)
    is_activated: Mapped[bool] = mapped_column(default=False)
    activated_at: Mapped[datetime] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    activations: Mapped[list["PromocodeActivation"]] = relationship(
        back_populates="promocode", cascade="all, delete-orphan"
    )

class PromocodeActivation(Base):
    __tablename__ = "vpn_promocode_useges"

    id: Mapped[int] = mapped_column(primary_key=True)
    promocode_id: Mapped[int] = mapped_column(ForeignKey("vpn_promocodes.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(default=datetime.now)

    promocode: Mapped[Promocode] = relationship(back_populates="activations")

    __table_args__ = (UniqueConstraint("promocode_id", "user_id", name="uq_vpn_promocode_user"),)

class EmailVerification(Base):
    __tablename__ = "vpn_email_verifications"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    attempts: Mapped[int] = mapped_column(default=0)
    last_sent_at: Mapped[datetime] = mapped_column(default=datetime.now)

