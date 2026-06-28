from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User
from app.services import email_service


async def create_notification(
    db: AsyncSession,
    user: User,
    title: str,
    message: str,
    send_email: bool = False,
) -> Notification:
    notification = Notification(user_id=user.id, title=title, message=message)
    db.add(notification)
    await db.flush()

    if send_email:
        await email_service.send_notification_email(user.email, user.username, title, message)

    return notification
