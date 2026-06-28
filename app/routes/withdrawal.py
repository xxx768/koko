from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import require_user, require_admin
from app.models.user import User
from app.schemas.withdrawal import (
    WithdrawalAdminDetailResponse,
    WithdrawalCreateRequest,
    WithdrawalFeeInfoResponse,
    WithdrawalListParams,
    WithdrawalRejectRequest,
    WithdrawalResponse,
    WithdrawalSettingResponse,
    WithdrawalSettingUpdateRequest,
)
from app.services import withdrawal_service

# ---------------------------------------------------------------------------
# User-facing router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/dashboard/withdrawal", tags=["Withdrawal"])


@router.get("/fee-info", response_model=WithdrawalFeeInfoResponse)
async def get_fee_info(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Bank details and fee amount the user must pay to proceed with a withdrawal."""
    setting = await withdrawal_service.get_or_create_setting(db)
    return WithdrawalFeeInfoResponse(
        fee_amount=setting.fee_amount,
        fee_bank_name=setting.fee_bank_name,
        fee_account_number=setting.fee_account_number,
        fee_account_name=setting.fee_account_name,
    )


@router.get("/current", response_model=WithdrawalResponse | None)
async def get_current_withdrawal(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """The user's active (or most recent) withdrawal request, shown on the dashboard."""
    request = await withdrawal_service.get_active_withdrawal(db, current_user.id)
    if not request:
        request = await withdrawal_service.get_latest_withdrawal(db, current_user.id)
    if not request:
        return None
    return WithdrawalResponse.from_orm_with_flags(request)


@router.get("/history", response_model=list[WithdrawalResponse])
async def get_withdrawal_history(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """All of the user's past and current withdrawal requests."""
    items = await withdrawal_service.list_user_withdrawals(db, current_user.id)
    return [WithdrawalResponse.from_orm_with_flags(r) for r in items]


@router.post("", response_model=WithdrawalResponse, status_code=status.HTTP_201_CREATED)
async def create_withdrawal(
    data: WithdrawalCreateRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Request a withdrawal. Reserves the amount from the user's balance immediately."""
    try:
        request = await withdrawal_service.create_withdrawal_request(db, current_user, data)
        return WithdrawalResponse.from_orm_with_flags(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{withdrawal_id}/proof", response_model=WithdrawalResponse)
async def upload_proof_of_payment(
    withdrawal_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload proof (PNG/JPEG) that the withdrawal fee has been paid."""
    try:
        request = await withdrawal_service.attach_proof_of_payment(
            db, current_user.id, withdrawal_id, file
        )
        return WithdrawalResponse.from_orm_with_flags(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Admin-facing router
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin", tags=["Admin – Withdrawals"])


@admin_router.get("/withdrawal-settings", response_model=WithdrawalSettingResponse)
async def get_withdrawal_settings(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await withdrawal_service.get_or_create_setting(db)


@admin_router.put("/withdrawal-settings", response_model=WithdrawalSettingResponse)
async def update_withdrawal_settings(
    data: WithdrawalSettingUpdateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await withdrawal_service.update_setting(db, data)


@admin_router.get("/withdrawals")
async def list_withdrawals(
    params: WithdrawalListParams = Depends(),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await withdrawal_service.list_withdrawals(db, params)
    return {
        "withdrawals": [WithdrawalResponse.from_orm_with_flags(r) for r in items],
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
    }


@admin_router.get("/withdrawals/{withdrawal_id}/proof-image")
async def get_proof_image(
    withdrawal_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the stored proof-of-payment as a JSON object containing a data-URI.
    The admin frontend should set `<img>.src` to the returned `data_uri` value.
    """
    try:
        data_uri = await withdrawal_service.get_proof_data_uri(db, withdrawal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"data_uri": data_uri}


@admin_router.patch("/withdrawals/{withdrawal_id}/verify", response_model=WithdrawalResponse)
async def verify_withdrawal(
    withdrawal_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve the withdrawal fee proof. Moves status to 'processing' and clears the proof image."""
    try:
        request = await withdrawal_service.verify_withdrawal(db, withdrawal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return WithdrawalResponse.from_orm_with_flags(request)


@admin_router.patch("/withdrawals/{withdrawal_id}/reject", response_model=WithdrawalResponse)
async def reject_withdrawal(
    withdrawal_id: int,
    body: WithdrawalRejectRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject the withdrawal fee proof. Refunds the amount to the user and clears the proof image."""
    try:
        request = await withdrawal_service.reject_withdrawal(db, withdrawal_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return WithdrawalResponse.from_orm_with_flags(request)


@admin_router.patch("/withdrawals/{withdrawal_id}/complete", response_model=WithdrawalResponse)
async def complete_withdrawal(
    withdrawal_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mark a processing withdrawal as fully completed (payout sent)."""
    try:
        request = await withdrawal_service.complete_withdrawal(db, withdrawal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return WithdrawalResponse.from_orm_with_flags(request)