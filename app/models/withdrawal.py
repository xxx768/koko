# import enum
# from datetime import datetime, timezone

# from sqlalchemy import (
#     DateTime,
#     Enum,
#     ForeignKey,
#     Integer,
#     Numeric,
#     String,
#     Text,
# )
# from sqlalchemy.orm import Mapped, mapped_column, relationship

# from app.database.base import Base
# from app.models.user import User


# class WithdrawalStatus(str, enum.Enum):
#     pending_payment = "pending_payment"          # request created, waiting for user to pay the fee
#     pending_verification = "pending_verification"  # user uploaded proof, waiting for admin review
#     processing = "processing"                     # admin verified the fee payment, payout in progress
#     completed = "completed"                       # admin marked the payout as done
#     rejected = "rejected"                          # admin rejected the proof of payment


# class WithdrawalRequest(Base):
#     __tablename__ = "withdrawal_requests"

#     id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
#     user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

#     # Amount the user wants to withdraw (already deducted from their balance at request time)
#     amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)

#     # Destination bank details supplied by the user
#     bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
#     account_number: Mapped[str] = mapped_column(String(34), nullable=False)
#     account_name: Mapped[str] = mapped_column(String(100), nullable=False)

#     # The fee the user was required to pay, captured at request time so later admin
#     # changes to the global setting don't retroactively change this request's fee.
#     fee_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)

#     status: Mapped[WithdrawalStatus] = mapped_column(
#         Enum(WithdrawalStatus), default=WithdrawalStatus.pending_payment, nullable=False, index=True
#     )

#     # Path (relative to the uploads dir) to the proof-of-payment image, set once the user uploads it
#     proof_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
#     proof_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

#     # Admin review metadata
#     admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
#     reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
#     completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

#     created_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
#     )
#     updated_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True),
#         default=lambda: datetime.now(timezone.utc),
#         onupdate=lambda: datetime.now(timezone.utc),
#         nullable=False,
#     )

#     user: Mapped["User"] = relationship("User", back_populates="withdrawal_requests")  # noqa: F821

#     def __repr__(self) -> str:
#         return f"<WithdrawalRequest id={self.id} user_id={self.user_id} status={self.status}>"


# # Statuses that count as "active" — a user may only have one of these open at a time
# ACTIVE_WITHDRAWAL_STATUSES = (
#     WithdrawalStatus.pending_payment,
#     WithdrawalStatus.pending_verification,
#     WithdrawalStatus.processing,
# )

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.user import User


class WithdrawalStatus(str, enum.Enum):
    pending_payment = "pending_payment"            # request created, waiting for user to pay the fee
    pending_verification = "pending_verification"  # user uploaded proof, waiting for admin review
    processing = "processing"                      # admin verified the fee payment, payout in progress
    completed = "completed"                        # admin marked the payout as done
    rejected = "rejected"                          # admin rejected the proof of payment


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Amount the user wants to withdraw (already deducted from their balance at request time)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)

    # Destination bank details supplied by the user
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_number: Mapped[str] = mapped_column(String(34), nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # The fee the user was required to pay, captured at request time so later admin
    # changes to the global setting don't retroactively change this request's fee.
    fee_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)

    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus),
        default=WithdrawalStatus.pending_payment,
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------------------------
    # Proof of payment stored as a base64-encoded data-URI string.
    # Format: "data:<mime>;base64,<data>"
    # This avoids relying on the local filesystem (which is wiped on redeploy).
    # The value is cleared (set to NULL) once the admin verifies OR rejects the
    # request so sensitive payment screenshots are not kept indefinitely.
    # -----------------------------------------------------------------------
    proof_image_b64: Mapped[str | None] = mapped_column(Text, nullable=True)

    # MIME type stored separately so callers can reconstruct a data-URI without
    # having to parse the stored string.
    proof_image_mime: Mapped[str | None] = mapped_column(String(20), nullable=True)

    proof_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Admin review metadata
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="withdrawal_requests")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<WithdrawalRequest id={self.id} user_id={self.user_id} status={self.status}>"
        )


# Statuses that count as "active" — a user may only have one of these open at a time
ACTIVE_WITHDRAWAL_STATUSES = (
    WithdrawalStatus.pending_payment,
    WithdrawalStatus.pending_verification,
    WithdrawalStatus.processing,
)
