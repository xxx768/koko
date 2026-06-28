from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class DailyBonusSetting(Base):
    __tablename__ = "daily_bonus_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bonus_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0.00, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
