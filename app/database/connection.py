from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.database.base import Base

settings = get_settings()

connect_args: dict = {}
if settings.is_sqlite:
    connect_args = {"check_same_thread": False}

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=connect_args,
)


async def init_db() -> None:
    """Create all tables on startup (dev). Use Alembic for production."""
    from app.models import (  # noqa: F401
        user,
        verification_code,
        notification,
        blacklisted_token,
        daily_bonus_claim,
        daily_bonus_setting,
        survey,
        withdrawal,
        withdrawal_setting,
        referral,
        announcement, 
        password_reset_code,      
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    await engine.dispose()
