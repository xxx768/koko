from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.user import User



class ReferralSetting(Base):
    """Singleton table — only one row, managed by admin."""

    __tablename__ = "referral_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ReferralSetting reward={self.reward_amount} enabled={self.is_enabled}>"


class Referral(Base):
    """Tracks each referral relationship and its reward state."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # The user who shared their code
    referrer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The new user who signed up with the code
    referred_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Reward is paid out after the referred user completes their first withdrawal fee payment
    reward_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reward_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    reward_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")  # noqa: F821
    referred: Mapped["User"] = relationship("User", foreign_keys=[referred_id], back_populates="referral_received")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Referral referrer={self.referrer_id} referred={self.referred_id} paid={self.reward_paid}>"
