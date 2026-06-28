from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import require_user
from app.models.user import User
from app.schemas.referral import ReferralStatsResponse
from app.services import referral_service

router = APIRouter(prefix="/referral", tags=["Referral"])


@router.get("/stats", response_model=ReferralStatsResponse)
async def get_referral_stats(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's referral code and stats."""
    return await referral_service.get_referral_stats(db, current_user)
