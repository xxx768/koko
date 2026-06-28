

"""
withdrawal_service.py

Key design decisions
--------------------
* Proof-of-payment images are stored as base64-encoded strings inside the
  database (column `proof_image_b64`) rather than on the local filesystem.
  This makes the data survive redeployments and removes the need for a
  persistent volume for this feature.

* The raw base64 value is ONLY ever returned to admin endpoints.  The regular
  user-facing responses expose only a boolean flag (`has_proof_image`).

* Once an admin verifies OR rejects a withdrawal request the stored image is
  immediately nulled out from the database.  This limits the window during
  which sensitive payment screenshots are retained.

Security controls
-----------------
* Content-type header checked against allow-list (PNG / JPEG only).
* File extension checked independently of the content-type header.
* Magic-byte validation: the raw bytes are inspected to confirm the file is
  actually a PNG or JPEG, regardless of what the client claims.
* Hard 5 MB size cap enforced before base64 encoding.
* Empty-file guard.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone, timedelta
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.withdrawal import (
    ACTIVE_WITHDRAWAL_STATUSES,
    WithdrawalRequest,
    WithdrawalStatus,
)
from app.models.withdrawal_setting import WithdrawalSetting
from app.schemas.withdrawal import (
    WithdrawalCreateRequest,
    WithdrawalListParams,
    WithdrawalSettingUpdateRequest,
)

# ---------------------------------------------------------------------------
# Proof-image validation constants
# ---------------------------------------------------------------------------

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset({"image/png", "image/jpeg"})
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg"})
MAX_PROOF_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB

# Magic bytes (file signatures) for supported image types.
# Checked against the raw uploaded bytes to prevent content-type spoofing.
_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_image_magic(content_type: str, data: bytes) -> None:
    """Raise ValueError if the file's magic bytes don't match the declared MIME type."""
    expected_signatures = _MAGIC_SIGNATURES.get(content_type, [])
    for sig in expected_signatures:
        if data[: len(sig)] == sig:
            return
    raise ValueError(
        "File content does not match the declared image type. "
        "Only genuine PNG and JPEG images are accepted."
    )


def _build_data_uri(mime: str, data: bytes) -> str:
    """Return a base64 data-URI string for *data*."""
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def _read_and_validate_proof(file: UploadFile) -> tuple[bytes, str]:
    """
    Read, validate, and return (raw_bytes, mime_type).

    Raises ValueError with a user-friendly message on any validation failure.
    The caller is responsible for committing / discarding the data.
    """
    # 1. Extension check (independent of Content-Type header)
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{ext}'. Only .png, .jpg, and .jpeg are accepted."
        )

    # 2. Content-Type header check
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Unsupported content type '{content_type}'. Only PNG and JPEG images are accepted."
        )

    # 3. Read into memory
    data = await file.read()

    # 4. Empty-file guard
    if not data:
        raise ValueError("The uploaded file is empty.")

    # 5. Size cap
    if len(data) > MAX_PROOF_SIZE_BYTES:
        size_mb = len(data) / (1024 * 1024)
        raise ValueError(
            f"Image is too large ({size_mb:.1f} MB). Maximum allowed size is 5 MB."
        )

    # 6. Magic-byte validation (prevents content-type spoofing)
    _validate_image_magic(content_type, data)

    return data, content_type


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

async def get_or_create_setting(db: AsyncSession) -> WithdrawalSetting:
    result = await db.execute(select(WithdrawalSetting).limit(1))
    setting = result.scalar_one_or_none()
    if not setting:
        setting = WithdrawalSetting()
        db.add(setting)
        await db.flush()
    return setting


async def update_setting(
    db: AsyncSession, data: WithdrawalSettingUpdateRequest
) -> WithdrawalSetting:
    setting = await get_or_create_setting(db)
    setting.min_balance = data.min_balance
    setting.fee_amount = data.fee_amount
    setting.fee_bank_name = data.fee_bank_name
    setting.fee_account_number = data.fee_account_number
    setting.fee_account_name = data.fee_account_name
    setting.daily_withdrawal_limit = data.daily_withdrawal_limit 
    return setting


# ---------------------------------------------------------------------------
# User-facing actions
# ---------------------------------------------------------------------------

async def get_active_withdrawal(
    db: AsyncSession, user_id: int
) -> WithdrawalRequest | None:
    result = await db.execute(
        select(WithdrawalRequest).where(
            WithdrawalRequest.user_id == user_id,
            WithdrawalRequest.status.in_(ACTIVE_WITHDRAWAL_STATUSES),
        )
    )
    return result.scalar_one_or_none()


async def _count_withdrawals_last_48h(db: AsyncSession, user_id: int) -> tuple[int, datetime | None]:
    """Returns (count, oldest_created_at) of requests made in the last 48 hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    result = await db.execute(
        select(WithdrawalRequest)
        .where(
            WithdrawalRequest.user_id == user_id,
            WithdrawalRequest.created_at >= since,
        )
        .order_by(WithdrawalRequest.created_at.asc())
    )
    requests = list(result.scalars().all())
    oldest = requests[0].created_at if requests else None
    return len(requests), oldest


async def create_withdrawal_request(
    db: AsyncSession, user: User, data: WithdrawalCreateRequest
) -> WithdrawalRequest:
    setting = await get_or_create_setting(db)

    if await get_active_withdrawal(db, user.id):
        raise ValueError("You already have a withdrawal request in progress.")

    if float(user.balance) < float(setting.min_balance):
        raise ValueError(
            f"Your balance must be at least ₦{float(setting.min_balance):,.2f} to request a withdrawal."
        )

    if float(data.amount) > float(user.balance):
        raise ValueError("Withdrawal amount cannot exceed your balance.")

    # 48-hour limit check
    count, oldest = await _count_withdrawals_last_48h(db, user.id)
    if count >= setting.daily_withdrawal_limit:
        reset_at = oldest + timedelta(hours=48)
        now = datetime.now(timezone.utc)
        remaining = reset_at - now
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes = remainder // 60
        raise ValueError(
            f"You have reached your withdrawal limit of {setting.daily_withdrawal_limit} "
            f"request(s) per 48 hours. You can make another withdrawal in "
            f"{hours}h {minutes}m."
        )

    user.balance = float(user.balance) - float(data.amount)

    request = WithdrawalRequest(
        user_id=user.id,
        amount=data.amount,
        bank_name=data.bank_name,
        account_number=data.account_number,
        account_name=data.account_name,
        fee_amount=setting.fee_amount,
        status=WithdrawalStatus.pending_payment,
    )
    db.add(request)
    await db.flush()
    return request

# async def create_withdrawal_request(
#     db: AsyncSession, user: User, data: WithdrawalCreateRequest
# ) -> WithdrawalRequest:
#     setting = await get_or_create_setting(db)

#     if await get_active_withdrawal(db, user.id):
#         raise ValueError("You already have a withdrawal request in progress.")

#     if float(user.balance) < float(setting.min_balance):
#         raise ValueError(
#             f"Your balance must be at least ₦{float(setting.min_balance):,.2f} to request a withdrawal."
#         )

#     if float(data.amount) > float(user.balance):
#         raise ValueError("Withdrawal amount cannot exceed your balance.")

#     user.balance = float(user.balance) - float(data.amount)

#     request = WithdrawalRequest(
#         user_id=user.id,
#         amount=data.amount,
#         bank_name=data.bank_name,
#         account_number=data.account_number,
#         account_name=data.account_name,
#         fee_amount=setting.fee_amount,
#         status=WithdrawalStatus.pending_payment,
#     )
#     db.add(request)
#     await db.flush()
#     return request


async def get_user_withdrawal(
    db: AsyncSession, user_id: int, withdrawal_id: int
) -> WithdrawalRequest:
    result = await db.execute(
        select(WithdrawalRequest).where(
            WithdrawalRequest.id == withdrawal_id,
            WithdrawalRequest.user_id == user_id,
        )
    )
    request = result.scalar_one_or_none()
    if not request:
        raise ValueError("Withdrawal request not found.")
    return request


async def get_latest_withdrawal(
    db: AsyncSession, user_id: int
) -> WithdrawalRequest | None:
    result = await db.execute(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.user_id == user_id)
        .order_by(WithdrawalRequest.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_user_withdrawals(
    db: AsyncSession, user_id: int
) -> list[WithdrawalRequest]:
    result = await db.execute(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.user_id == user_id)
        .order_by(WithdrawalRequest.created_at.desc())
    )
    return list(result.scalars().all())


async def attach_proof_of_payment(
    db: AsyncSession,
    user_id: int,
    withdrawal_id: int,
    file: UploadFile,
) -> WithdrawalRequest:
    """
    Validate the uploaded image and store it as a base64 data-URI in the DB.
    If a previous proof exists for this request it is overwritten in-place
    (no orphaned files, because there are no files).
    """
    request = await get_user_withdrawal(db, user_id, withdrawal_id)

    if request.status != WithdrawalStatus.pending_payment:
        raise ValueError("This withdrawal request is not awaiting payment proof.")

    raw_bytes, mime_type = await _read_and_validate_proof(file)
    data_uri = _build_data_uri(mime_type, raw_bytes)

    request.proof_image_b64 = data_uri
    request.proof_image_mime = mime_type
    request.proof_uploaded_at = datetime.now(timezone.utc)
    request.status = WithdrawalStatus.pending_verification
    return request


# ---------------------------------------------------------------------------
# Admin-facing actions
# ---------------------------------------------------------------------------

async def list_withdrawals(
    db: AsyncSession, params: WithdrawalListParams
) -> tuple[list[WithdrawalRequest], int]:
    query = select(WithdrawalRequest)
    if params.status is not None:
        query = query.where(WithdrawalRequest.status == params.status)

    count_result = await db.execute(
        select(WithdrawalRequest.id).filter(query.whereclause)  # type: ignore[arg-type]
    )
    total = len(count_result.all())

    query = (
        query.order_by(WithdrawalRequest.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_withdrawal(db: AsyncSession, withdrawal_id: int) -> WithdrawalRequest:
    request = await db.get(WithdrawalRequest, withdrawal_id)
    if not request:
        raise ValueError("Withdrawal request not found.")
    return request


async def get_proof_data_uri(db: AsyncSession, withdrawal_id: int) -> str:
    """
    Return the stored data-URI for admin viewing.
    Raises ValueError if the withdrawal doesn't exist or has no proof attached.
    This is the *only* place the raw base64 ever leaves the service layer.
    """
    request = await get_withdrawal(db, withdrawal_id)
    if not request.proof_image_b64:
        raise ValueError("No proof of payment has been uploaded for this withdrawal.")
    return request.proof_image_b64


def _clear_proof(request: WithdrawalRequest) -> None:
    """
    Erase the stored proof image from the DB row.
    Called after the admin makes a final decision so screenshots aren't kept indefinitely.
    """
    request.proof_image_b64 = None
    request.proof_image_mime = None


async def verify_withdrawal(
    db: AsyncSession, withdrawal_id: int
) -> WithdrawalRequest:
    request = await get_withdrawal(db, withdrawal_id)
    if request.status != WithdrawalStatus.pending_verification:
        raise ValueError("This withdrawal is not awaiting verification.")

    request.status = WithdrawalStatus.processing
    request.reviewed_at = datetime.now(timezone.utc)

    # Delete the proof image now that admin has made a decision.
    _clear_proof(request)

    # Pay out the referral reward to whoever referred this user (if any, only once).
    user = await db.get(User, request.user_id)
    if user:
        from app.services.referral_service import process_referral_reward_on_withdrawal
        await process_referral_reward_on_withdrawal(db, user)

    return request


async def reject_withdrawal(
    db: AsyncSession, withdrawal_id: int, reason: str
) -> WithdrawalRequest:
    request = await get_withdrawal(db, withdrawal_id)
    if request.status != WithdrawalStatus.pending_verification:
        raise ValueError("This withdrawal is not awaiting verification.")

    # Refund the reserved amount to the user's balance.
    user = await db.get(User, request.user_id)
    if user:
        user.balance = float(user.balance) + float(request.amount)

    request.status = WithdrawalStatus.rejected
    request.admin_note = reason
    request.reviewed_at = datetime.now(timezone.utc)

    # Delete the proof image now that admin has made a decision.
    _clear_proof(request)

    return request


async def complete_withdrawal(
    db: AsyncSession, withdrawal_id: int
) -> WithdrawalRequest:
    request = await get_withdrawal(db, withdrawal_id)
    if request.status != WithdrawalStatus.processing:
        raise ValueError("This withdrawal is not in processing status.")
    request.status = WithdrawalStatus.completed
    request.completed_at = datetime.now(timezone.utc)
    return request