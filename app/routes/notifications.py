from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.announcement import Announcement
from app.database.session import get_db
from app.dependencies import require_user
from app.models.user import User
from app.schemas.user import NotificationResponse
from app.services.user_service import get_user_notifications, get_unread_count

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=dict)
async def get_notifications(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all notifications with unread count for the current user."""
    notifications = await get_user_notifications(db, current_user.id)
    unread = await get_unread_count(db, current_user.id)

    ann_result = await db.execute(
        select(Announcement)
        .where(Announcement.is_active == True)  # noqa: E712
        .order_by(Announcement.created_at.desc())
    )
    announcements = ann_result.scalars().all()

    return {
        "unread_count": unread,
        "notifications": [NotificationResponse.model_validate(n) for n in notifications],
        "announcements": [
            {
                "id": a.id,
                "title": a.title,
                "message": a.message,
                "created_at": a.created_at.isoformat(),
                "type": "announcement",
            }
            for a in announcements
        ],
    }