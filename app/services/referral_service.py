import logging
import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import Referral, ReferralSetting
from app.models.user import User
from app.schemas.referral import ReferralSettingUpdateRequest, ReferralStatsResponse

logger = logging.getLogger(__name__)

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def generate_referral_code() -> str:
    """Generate a cryptographically random 8-character alphanumeric referral code."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def get_unique_referral_code(db: AsyncSession) -> str:
    """Generate a referral code guaranteed to be unique in the DB."""
    while True:
        code = generate_referral_code()
        existing = await db.execute(select(User.id).where(User.referral_code == code))
        if existing.scalar_one_or_none() is None:
            return code


# ---------------------------------------------------------------------------
# Admin — settings
# ---------------------------------------------------------------------------

async def get_or_create_setting(db: AsyncSession) -> ReferralSetting:
    result = await db.execute(select(ReferralSetting).limit(1))
    setting = result.scalar_one_or_none()
    if not setting:
        setting = ReferralSetting()
        db.add(setting)
        await db.flush()
    return setting


async def update_setting(db: AsyncSession, data: ReferralSettingUpdateRequest) -> ReferralSetting:
    setting = await get_or_create_setting(db)
    setting.reward_amount = data.reward_amount
    setting.is_enabled = data.is_enabled
    return setting


# ---------------------------------------------------------------------------
# Registration hook
# ---------------------------------------------------------------------------

async def apply_referral_on_register(db: AsyncSession, new_user: User, referral_code: str) -> None:
    """
    Called during registration when a referral code is provided.
    Creates a Referral record linking the referrer to the new user.
    The reward is NOT paid yet — it's paid after the referred user's first
    successful withdrawal fee payment.
    """
    if not referral_code:
        return

    referrer_result = await db.execute(
        select(User).where(User.referral_code == referral_code.upper().strip())
    )
    referrer = referrer_result.scalar_one_or_none()

    if not referrer:
        logger.warning("Referral code '%s' not found; ignoring.", referral_code)
        return

    if referrer.id == new_user.id:
        logger.warning("User %s tried to refer themselves; ignoring.", new_user.id)
        return

    # Prevent a user from being referred more than once
    existing = await db.execute(select(Referral.id).where(Referral.referred_id == new_user.id))
    if existing.scalar_one_or_none():
        return

    setting = await get_or_create_setting(db)
    referral = Referral(
        referrer_id=referrer.id,
        referred_id=new_user.id,
        reward_amount=setting.reward_amount,
    )
    db.add(referral)
    logger.info("Referral recorded: referrer=%s referred=%s", referrer.id, new_user.id)


# ---------------------------------------------------------------------------
# Withdrawal hook — pay out reward
# ---------------------------------------------------------------------------

async def process_referral_reward_on_withdrawal(db: AsyncSession, referred_user: User) -> None:
    """
    Called when a referred user's first withdrawal fee is verified (paid).
    Pays the referrer their reward if not already paid.
    """
    result = await db.execute(
        select(Referral).where(
            Referral.referred_id == referred_user.id,
            Referral.reward_paid == False,  # noqa: E712
        )
    )
    referral = result.scalar_one_or_none()

    if not referral:
        return  # No pending referral for this user

    setting = await get_or_create_setting(db)
    if not setting.is_enabled or setting.reward_amount <= 0:
        logger.info("Referral rewards disabled or zero; skipping payout for referred=%s", referred_user.id)
        return

    referrer = await db.get(User, referral.referrer_id)
    if not referrer:
        return

    # Credit the referrer
    referrer.balance = referrer.balance + referral.reward_amount
    referral.reward_paid = True
    referral.reward_paid_at = datetime.now(timezone.utc)

    logger.info(
        "Referral reward ₦%s paid to referrer=%s for referred=%s",
        referral.reward_amount,
        referrer.id,
        referred_user.id,
    )

    # Send in-app notification to the referrer
    try:
        from app.services.notification_service import create_notification
        await create_notification(
            db,
            referrer,
            "Referral Reward Earned!",
            f"You earned ₦{float(referral.reward_amount):,.2f} because your referral "
            f"({referred_user.username}) completed their first withdrawal fee payment.",
            send_email=False,
        )
    except Exception as exc:
        logger.warning("Could not send referral reward notification: %s", exc)


# ---------------------------------------------------------------------------
# User stats
# ---------------------------------------------------------------------------

async def get_referral_stats(db: AsyncSession, user: User) -> ReferralStatsResponse:
    result = await db.execute(select(Referral).where(Referral.referrer_id == user.id))
    referrals = list(result.scalars().all())

    paid = [r for r in referrals if r.reward_paid]
    pending = [r for r in referrals if not r.reward_paid]
    total_earned = sum(r.reward_amount for r in paid)

    return ReferralStatsResponse(
        referral_code=user.referral_code or "",
        total_referrals=len(referrals),
        paid_referrals=len(paid),
        pending_referrals=len(pending),
        total_earned=total_earned,
    )
