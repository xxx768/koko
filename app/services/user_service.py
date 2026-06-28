from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User
from app.schemas.user import UserUpdateRequest


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def update_user_profile(db: AsyncSession, user: User, data: UserUpdateRequest) -> User:
    if data.username is not None:
        existing = await db.execute(select(User.id).where(User.username == data.username, User.id != user.id))
        if existing.scalar_one_or_none():
            raise ValueError("Username already taken.")
        user.username = data.username.strip()

    if data.phone_number is not None:
        existing = await db.execute(
            select(User.id).where(User.phone_number == data.phone_number, User.id != user.id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Phone number already in use.")
        user.phone_number = data.phone_number.strip()

    return user


async def get_user_notifications(db: AsyncSession, user_id: int) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def get_unread_count(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id, Notification.is_read == False  # noqa: E712
        )
    )
    return len(result.scalars().all())


async def mark_notification_read(db: AsyncSession, user_id: int, notification_id: int) -> Notification:
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise ValueError("Notification not found.")
    notification.is_read = True
    return notification
