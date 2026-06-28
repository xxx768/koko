from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import require_user
from app.models.user import User
from app.schemas.daily_bonus import DailyBonusStatusResponse
from app.schemas.survey import SurveyResponse, SurveySubmissionRequest, SurveySubmissionResponse
from app.services import daily_bonus_service, survey_service
from app.services.user_service import get_unread_count

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
async def dashboard(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """User dashboard with balance and unread notification count."""
    unread = await get_unread_count(db, current_user.id)
    bonus_status = await daily_bonus_service.get_bonus_status(db, current_user)
    return {
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "balance": f"₦{float(current_user.balance):,.2f}",
        "balance_raw": float(current_user.balance),
        "unread_notifications": unread,
        "daily_bonus": {
            "can_claim": bonus_status.can_claim,
            "next_claim_at": bonus_status.next_claim_at,
            "bonus_amount": bonus_status.bonus_amount,
            "last_claimed_at": bonus_status.last_claimed_at,
        },
    }


@router.get("/surveys", response_model=list[SurveyResponse])
async def list_surveys(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Return active surveys available to the current user."""
    return await survey_service.list_active_surveys_for_user(db, current_user)


@router.post("/surveys/{survey_id}/submit", response_model=SurveySubmissionResponse)
async def submit_survey(
    survey_id: int,
    data: SurveySubmissionRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a survey response and reward the user if eligible."""
    try:
        survey = await survey_service.get_survey(db, survey_id)
        submission = await survey_service.submit_survey(db, survey, current_user, data)
        return submission
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/bonus", response_model=DailyBonusStatusResponse)
async def get_bonus_status(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's daily bonus eligibility."""
    return await daily_bonus_service.get_bonus_status(db, current_user)


@router.post("/bonus/claim", response_model=DailyBonusStatusResponse)
async def claim_daily_bonus(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Claim the daily bonus if 24 hours have passed since the last claim."""
    try:
        _, status = await daily_bonus_service.claim_bonus(db, current_user)
        return status
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
