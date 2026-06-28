import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user, nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0.00, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Referral — unique code assigned at registration
    referral_code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    verification_codes: Mapped[list["VerificationCode"]] = relationship(  # noqa: F821
        "VerificationCode", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    withdrawal_requests: Mapped[list["WithdrawalRequest"]] = relationship(  # noqa: F821
        "WithdrawalRequest", back_populates="user", cascade="all, delete-orphan"
    )
    # Referrals this user has made (as referrer)
    referrals_made: Mapped[list["Referral"]] = relationship(  # noqa: F821
        "Referral", foreign_keys="[Referral.referrer_id]",
        back_populates="referrer", cascade="all, delete-orphan"
    )
    # The referral record where this user was referred (at most one)
    referral_received: Mapped[list["Referral"]] = relationship(  # noqa: F821
        "Referral", foreign_keys="[Referral.referred_id]",
        back_populates="referred", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
