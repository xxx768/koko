from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class WithdrawalSetting(Base):
    """Singleton settings row (mirrors the daily_bonus_setting pattern)."""

    __tablename__ = "withdrawal_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Minimum balance a user must have before they're allowed to request a withdrawal
    min_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0.00, nullable=False)

    # Fee the user must pay (to the bank details below) before a withdrawal is reviewed
    fee_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0.00, nullable=False)

    # Bank account the fee should be paid into
    fee_bank_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    fee_account_number: Mapped[str] = mapped_column(String(34), default="", nullable=False)
    fee_account_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)

    daily_withdrawal_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )