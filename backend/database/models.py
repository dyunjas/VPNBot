from datetime import datetime, timezone
import enum
from sqlalchemy import (
    String,
    BigInteger,
    Integer,
    Boolean,
    ForeignKey,
    Enum,
    UniqueConstraint,
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
    subscription_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    remnawave_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    remnawave_user_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
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

class SubscriptionPlan(Base):
    __tablename__ = "vpn_subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    price: Mapped[int] = mapped_column()
    period_days: Mapped[int] = mapped_column(default=30)
    gb_limit: Mapped[int] = mapped_column(default=0, nullable=False)

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
    subscription_token: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)

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
