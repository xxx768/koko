from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.services.analytics_service import get_analytics

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])


@router.get("")
async def analytics(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Platform analytics, revenue report, and transaction log."""
    return await get_analytics(db)