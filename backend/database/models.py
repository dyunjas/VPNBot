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
    DateTime,
    Numeric,
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
    support = "support"

class SupportMessageDirection(str, enum.Enum):
    user = "user"
    support = "support"


class BroadcastJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


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
    traffic_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
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
    referral_percent: Mapped[int] = mapped_column(default=25)

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


class PartnerLink(Base):
    __tablename__ = "vpn_partner_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    attributions: Mapped[list["PartnerAttribution"]] = relationship(
        "PartnerAttribution",
        back_populates="partner_link",
        cascade="all, delete-orphan",
    )


class PartnerAttribution(Base):
    __tablename__ = "vpn_partner_attributions"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_partner_attributions_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_link_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_partner_links.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    partner_link: Mapped["PartnerLink"] = relationship(
        "PartnerLink",
        back_populates="attributions",
    )
    user: Mapped["User"] = relationship("User")

class SubscriptionPlan(Base):
    __tablename__ = "vpn_subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    price: Mapped[int] = mapped_column()
    period_days: Mapped[int] = mapped_column(default=30)
    gb_limit: Mapped[int] = mapped_column(default=0, nullable=False)
    device_limit: Mapped[int] = mapped_column(default=3, nullable=False)
    display_order: Mapped[int] = mapped_column(default=0, nullable=False)
    purchase_limit: Mapped[int] = mapped_column(default=0, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    topups: Mapped[list["SubscriptionTopup"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )

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
    gb_left: Mapped[int] = mapped_column(default=0, nullable=False)
    device_limit: Mapped[int] = mapped_column(default=3, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SubscriptionTopup(Base):
    __tablename__ = "vpn_subscription_topups"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    gb: Mapped[float] = mapped_column("gb_added", Numeric(10, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="topups")


class UserActivity(Base):
    __tablename__ = "vpn_user_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("vpn_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    amount: Mapped[int | None] = mapped_column(nullable=True)
    traffic_gb: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("vpn_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_id_ref: Mapped[int | None] = mapped_column(
        ForeignKey("vpn_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
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


class BroadcastHistory(Base):
    __tablename__ = "vpn_broadcast_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    text: Mapped[str] = mapped_column(String(4096), nullable=False)
    parse_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="HTML")
    include_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_image: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[BroadcastJobStatus] = mapped_column(
        Enum(BroadcastJobStatus),
        default=BroadcastJobStatus.queued,
        nullable=False,
    )
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Admin(Base):
    __tablename__ = "vpn_admins"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)

    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole),
        default=AdminRole.support,
        nullable=False
    )

    login: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
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


class AdminLoginEvent(Base):
    __tablename__ = "vpn_admin_login_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("vpn_admins.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class AdminActionLog(Base):
    __tablename__ = "vpn_admin_action_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("vpn_admins.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


