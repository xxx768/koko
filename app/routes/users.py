from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import get_current_user, require_user
from app.models.user import User
from app.schemas.user import NotificationResponse, UserResponse, UserUpdateRequest
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(require_user)):
    """Get the authenticated user's profile."""
    return current_user


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    data: UserUpdateRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile (username, phone)."""
    try:
        user = await user_service.update_user_profile(db, current_user, data)
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all notifications for the current user."""
    return await user_service.get_user_notifications(db, current_user.id)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    try:
        return await user_service.mark_notification_read(db, current_user.id, notification_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
