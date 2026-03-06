from datetime import datetime, timezone
import enum
from decimal import Decimal

from sqlalchemy import (
    String,
    BigInteger,
    Boolean,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
    Numeric,
    DateTime
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)


class Base(DeclarativeBase):
    pass


class KeyStatus(str, enum.Enum):
    active = "active"
    deleted = "deleted"

class SubStatus(str, enum.Enum):
    active = "active"
    past_due = "past_due"
    expired = "expired"
    canceled = "canceled"

class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class AdminRole(str, enum.Enum):
    superadmin = "superadmin"
    manager = "manager"
    support = "support"

class SupportMessageDirection(str, enum.Enum):
    user = "user"
    support = "support"


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
    subscription_token: Mapped[str | None] = mapped_column(
        String(36), unique=True, index=True, nullable=True
    )

    banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    keys: Mapped[list["Key"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    referral_account: Mapped["ReferralAccount"] = relationship(
        "ReferralAccount",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    admin: Mapped["Admin"] = relationship(
        "Admin",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    devices: Mapped[list["UserDevice"]] = relationship(
        "UserDevice",
        back_populates="user",
        cascade="all, delete-orphan",
    )

class UserDevice(Base):
    __tablename__ = "vpn_user_devices"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    hwid: Mapped[str] = mapped_column(String(128), nullable=False)

    device_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_os: Mapped[str | None] = mapped_column(String(32), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    device_locale: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(128), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="devices",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "hwid", name="uq_vpn_user_device_hwid"),
    )

class ReferralAccount(Base):
    __tablename__ = "vpn_referral_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_users.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )

    invited_count: Mapped[int] = mapped_column(default=0)
    referral_balance: Mapped[int] = mapped_column(default=0)
    referral_percent: Mapped[int] = mapped_column(default=50)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(
        back_populates="referral_account"
    )

    withdrawals: Mapped[list["ReferralWithdrawal"]] = relationship(
        "ReferralWithdrawal",
        back_populates="referral_account",
        cascade="all, delete-orphan"
    )

class ReferralWithdrawal(Base):
    __tablename__ = "vpn_referral_withdrawals"

    id: Mapped[int] = mapped_column(primary_key=True)

    referral_account_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_referral_accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    amount: Mapped[int] = mapped_column(nullable=False)
    method: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus),
        default=WithdrawalStatus.pending
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    referral_account: Mapped["ReferralAccount"] = relationship(
        "ReferralAccount",
        back_populates="withdrawals"
    )

class Server(Base):
    __tablename__ = "vpn_servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[str] = mapped_column(String(64))
    inbound_tag: Mapped[str] = mapped_column(String(64))
    grpc_endpoint: Mapped[str] = mapped_column(String(128))
    public_host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(default=443)
    sni: Mapped[str] = mapped_column(String(255), default="telegram.com")
    fp: Mapped[str] = mapped_column(String(32), default="chrome")
    pbk: Mapped[str] = mapped_column(String(128))
    short_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    keys: Mapped[list["Key"]] = relationship(
        "Key", back_populates="server", cascade="all, delete-orphan"
    )

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubscriptionPlan(Base):
    __tablename__ = "vpn_subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    price: Mapped[int] = mapped_column()
    period_days: Mapped[int] = mapped_column(default=30)
    gb_limit: Mapped[int] = mapped_column(default=0, nullable=False)
    device_limit: Mapped[int] = mapped_column(default=5)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "vpn_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("vpn_users.id", ondelete="CASCADE"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("vpn_subscription_plans.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="subscriptions")

    status: Mapped[SubStatus] = mapped_column(Enum(SubStatus), default=SubStatus.active)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    devices_limit: Mapped[int] = mapped_column(default=5, nullable=False)
    devices_left: Mapped[int] = mapped_column(default=5, nullable=False)
    gb_left: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    next_renewal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    topups: Mapped[list["SubscriptionTopup"]] = relationship(
        "SubscriptionTopup",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class SubscriptionTopup(Base):
    __tablename__ = "vpn_subscription_topups"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    gb_added: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="topups",
    )


class Transaction(Base):
    __tablename__ = "vpn_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(255))
    amount: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    payment_system: Mapped[str] = mapped_column(String(32))

    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("vpn_users.id"))

    user: Mapped["User"] = relationship(back_populates="transactions")


class Promocode(Base):
    __tablename__ = "vpn_promocodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(default=0, nullable=False)
    usages: Mapped[int] = mapped_column(default=1)
    is_activated: Mapped[bool] = mapped_column(default=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    activations: Mapped[list["PromocodeActivation"]] = relationship(
        back_populates="promocode", cascade="all, delete-orphan"
    )


class PromocodeActivation(Base):
    __tablename__ = "vpn_promocode_useges"

    id: Mapped[int] = mapped_column(primary_key=True)
    promocode_id: Mapped[int] = mapped_column(ForeignKey("vpn_promocodes.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    promocode: Mapped[Promocode] = relationship(back_populates="activations")

    __table_args__ = (
        UniqueConstraint("promocode_id", "user_id", name="uq_vpn_promocode_user"),
    )

class Admin(Base):
    __tablename__ = "vpn_admins"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False
    )

    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole),
        default=AdminRole.support,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="admin",
        uselist=False
    )
