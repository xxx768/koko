from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import require_user
from app.models.user import User
from app.services.insights_service import get_insights

router = APIRouter(prefix="/api/insights", tags=["Insights"])


@router.get("")
async def insights(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's transaction history, weekly earnings chart, and lifetime overview."""
    return await get_insights(db, current_user)