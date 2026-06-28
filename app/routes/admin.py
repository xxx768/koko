from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.dependencies import require_admin
from app.models.user import User, UserRole
from app.models.withdrawal import WithdrawalStatus
from app.schemas.admin import (
    AdminCreateUserRequest,
    AdminNotifyUserRequest,
    AdminUpdateUserRequest,
    UserSearchParams,
)
from app.schemas.daily_bonus import DailyBonusSettingRequest, DailyBonusStatusResponse
from app.schemas.referral import ReferralSettingResponse, ReferralSettingUpdateRequest
from app.schemas.survey import SurveyCreateRequest, SurveyResponse
from app.schemas.user import UserResponse
from app.schemas.withdrawal import (
    WithdrawalListParams,
    WithdrawalRejectRequest,
    WithdrawalResponse,
    WithdrawalSettingResponse,
    WithdrawalSettingUpdateRequest,
)
from app.services import admin_service, daily_bonus_service, referral_service, survey_service, withdrawal_service
from app.services.notification_service import create_notification

from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=dict)
async def list_users(
    search: str | None = Query(None),
    role: UserRole | None = Query(None),
    is_suspended: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users with optional search and filters."""
    params = UserSearchParams(search=search, role=role, is_suspended=is_suspended, page=page, page_size=page_size)
    users, total = await admin_service.list_users(db, params)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": [UserResponse.model_validate(u) for u in users],
    }


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user's profile."""
    try:
        return await admin_service.get_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminCreateUserRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only). User is pre-verified."""
    try:
        return await admin_service.create_user(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: AdminUpdateUserRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update any user's details."""
    try:
        return await admin_service.update_user(db, user_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a user."""
    try:
        await admin_service.delete_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/users/{user_id}/suspend", response_model=UserResponse)
async def suspend_user(
    user_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Suspend a user account."""
    try:
        return await admin_service.suspend_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a suspended user account."""
    try:
        return await admin_service.activate_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/notify", status_code=status.HTTP_201_CREATED)
async def notify_user(
    user_id: int,
    data: AdminNotifyUserRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send an in-app (and optionally email) notification to a user."""
    try:
        target = await admin_service.get_user(db, user_id)
        notification = await create_notification(db, target, data.title, data.message, data.send_email)
        return {"message": "Notification sent.", "notification_id": notification.id}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/surveys", response_model=list[SurveyResponse])
async def list_surveys(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all surveys created by the admin."""
    return await survey_service.list_active_surveys(db)


@router.post("/surveys", response_model=SurveyResponse, status_code=status.HTTP_201_CREATED)
async def create_survey(
    data: SurveyCreateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new survey with questions and answer options."""
    survey = await survey_service.create_survey(db, data)
    return survey


@router.delete("/surveys/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_survey(
    survey_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a survey and all its related content."""
    try:
        await survey_service.delete_survey(db, survey_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/bonus", response_model=DailyBonusStatusResponse)
async def get_bonus_setting(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get the current daily bonus amount and status."""
    setting = await daily_bonus_service.get_or_create_setting(db)
    return DailyBonusStatusResponse(
        can_claim=True,
        next_claim_at=None,
        bonus_amount=float(setting.bonus_amount),
        last_claimed_at=None,
    )


@router.put("/bonus", response_model=DailyBonusStatusResponse)
async def update_bonus_setting(
    data: DailyBonusSettingRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Allow the admin to configure the daily bonus amount."""
    setting = await daily_bonus_service.update_bonus_setting(db, data)
    return DailyBonusStatusResponse(
        can_claim=True,
        next_claim_at=None,
        bonus_amount=float(setting.bonus_amount),
        last_claimed_at=None,
    )


# ---------------------------------------------------------------------------
# Withdrawal settings
# ---------------------------------------------------------------------------

@router.get("/withdrawal-settings", response_model=WithdrawalSettingResponse)
async def get_withdrawal_settings(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get the current withdrawal settings (min balance, fee, fee payment account)."""
    return await withdrawal_service.get_or_create_setting(db)


@router.put("/withdrawal-settings", response_model=WithdrawalSettingResponse)
async def update_withdrawal_settings(
    data: WithdrawalSettingUpdateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update the minimum balance, fee amount, and fee payment account details."""
    return await withdrawal_service.update_setting(db, data)


# ---------------------------------------------------------------------------
# Withdrawal requests
# ---------------------------------------------------------------------------

@router.get("/withdrawals", response_model=dict)
async def list_withdrawals(
    status_filter: WithdrawalStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List withdrawal requests, optionally filtered by status."""
    params = WithdrawalListParams(status=status_filter, page=page, page_size=page_size)
    requests, total = await withdrawal_service.list_withdrawals(db, params)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "withdrawals": [WithdrawalResponse.model_validate(w) for w in requests],
    }


@router.patch("/withdrawals/{withdrawal_id}/verify", response_model=WithdrawalResponse)
async def verify_withdrawal(
    withdrawal_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Verify the uploaded proof of fee payment; moves the request to 'processing'."""
    try:
        return await withdrawal_service.verify_withdrawal(db, withdrawal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/withdrawals/{withdrawal_id}/reject", response_model=WithdrawalResponse)
async def reject_withdrawal(
    withdrawal_id: int,
    data: WithdrawalRejectRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject the proof of fee payment; refunds the reserved balance back to the user."""
    try:
        return await withdrawal_service.reject_withdrawal(db, withdrawal_id, data.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/withdrawals/{withdrawal_id}/complete", response_model=WithdrawalResponse)
async def complete_withdrawal(
    withdrawal_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mark a withdrawal (already in 'processing') as completed once payout is done."""
    try:
        return await withdrawal_service.complete_withdrawal(db, withdrawal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/withdrawals/{withdrawal_id}/proof-image", include_in_schema=False)
async def get_withdrawal_proof_image(
    withdrawal_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Serve the proof-of-payment image for a withdrawal request (admin only)."""
    try:
        data_uri = await withdrawal_service.get_proof_data_uri(db, withdrawal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"data_uri": data_uri}

# ---------------------------------------------------------------------------
# Referral settings
# ---------------------------------------------------------------------------

@router.get("/referral-settings", response_model=ReferralSettingResponse)
async def get_referral_settings(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get the current referral reward amount and enabled status."""
    return await referral_service.get_or_create_setting(db)


@router.put("/referral-settings", response_model=ReferralSettingResponse)
async def update_referral_settings(
    data: ReferralSettingUpdateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update the referral reward amount and toggle referrals on/off."""
    return await referral_service.update_setting(db, data)


@router.get("/announcements", response_model=list[AnnouncementResponse])
async def list_announcements(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Announcement).order_by(Announcement.created_at.desc())
    )
    return result.scalars().all()


@router.post("/announcements", response_model=AnnouncementResponse, status_code=201)
async def create_announcement(
    data: AnnouncementCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ann = Announcement(title=data.title.strip(), message=data.message.strip())
    db.add(ann)
    await db.flush()
    return ann


@router.delete("/announcements/{ann_id}", status_code=204)
async def delete_announcement(
    ann_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ann = await db.get(Announcement, ann_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    await db.delete(ann)