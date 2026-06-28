from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_bonus_claim import DailyBonusClaim
from app.models.daily_bonus_setting import DailyBonusSetting
from app.models.user import User
from app.schemas.daily_bonus import DailyBonusSettingRequest, DailyBonusStatusResponse


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def get_or_create_setting(db: AsyncSession) -> DailyBonusSetting:
    setting = (await db.execute(select(DailyBonusSetting).order_by(DailyBonusSetting.id.asc()))).scalar_one_or_none()
    if setting is None:
        setting = DailyBonusSetting(bonus_amount=0.00)
        db.add(setting)
        await db.flush()
    return setting


async def update_bonus_setting(db: AsyncSession, data: DailyBonusSettingRequest) -> DailyBonusSetting:
    setting = await get_or_create_setting(db)
    setting.bonus_amount = data.amount
    return setting


async def get_bonus_status(db: AsyncSession, user: User) -> DailyBonusStatusResponse:
    setting = await get_or_create_setting(db)
    last_claim = (
        await db.execute(
            select(DailyBonusClaim)
            .where(DailyBonusClaim.user_id == user.id)
            .order_by(DailyBonusClaim.claimed_at.desc())
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    can_claim = True
    next_claim_at = None
    last_claimed_at = None

    if last_claim is not None:
        claimed_at = _normalize_datetime(last_claim.claimed_at)
        if claimed_at is not None:
            last_claimed_at = claimed_at.isoformat()
            next_claim_at = (claimed_at + timedelta(hours=24)).isoformat()
            can_claim = now >= claimed_at + timedelta(hours=24)

    return DailyBonusStatusResponse(
        can_claim=can_claim,
        next_claim_at=next_claim_at,
        bonus_amount=float(setting.bonus_amount),
        last_claimed_at=last_claimed_at,
    )


async def claim_bonus(db: AsyncSession, user: User) -> tuple[User, DailyBonusStatusResponse]:
    setting = await get_or_create_setting(db)
    if setting.bonus_amount <= 0:
        raise ValueError("Daily bonus amount is not set.")

    last_claim = (
        await db.execute(
            select(DailyBonusClaim)
            .where(DailyBonusClaim.user_id == user.id)
            .order_by(DailyBonusClaim.claimed_at.desc())
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    claimed_at = _normalize_datetime(last_claim.claimed_at) if last_claim is not None else None
    if claimed_at is not None and now < claimed_at + timedelta(hours=24):
        raise ValueError("You can claim the daily bonus again after 24 hours.")

    user.balance = float(user.balance) + float(setting.bonus_amount)
    claim = DailyBonusClaim(user_id=user.id, amount=setting.bonus_amount)
    db.add(claim)
    return user, await get_bonus_status(db, user)
