import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.blacklisted_token import BlacklistedToken
from app.models.user import User, UserRole
from app.models.verification_code import VerificationCode
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services import email_service
from app.services.jwt_service import create_access_token, create_refresh_token, decode_token
from app.services.security_service import (
    hash_password,
    verify_password,
    validate_password_strength,
    get_password_policy_message,
    generate_verification_code,
    hash_verification_code,
    verify_verification_code,
)

settings = get_settings()
logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    """Register a new user. Raises ValueError on validation failure."""

    # Password policy
    if not validate_password_strength(data.password):
        raise ValueError(get_password_policy_message())

    if data.password != data.confirm_password:
        raise ValueError("Passwords do not match.")

    # Uniqueness checks
    if await _email_exists(db, data.email):
        raise ValueError("An account with this email already exists.")
    if await _username_exists(db, data.username):
        raise ValueError("This username is already taken.")
    if await _phone_exists(db, data.phone_number):
        raise ValueError("An account with this phone number already exists.")

    # Generate a unique referral code for the new user
    from app.services.referral_service import get_unique_referral_code
    referral_code = await get_unique_referral_code(db)

    user = User(
        username=data.username.strip(),
        email=data.email.lower().strip(),
        phone_number=data.phone_number.strip(),
        hashed_password=hash_password(data.password),
        role=UserRole.user,
        is_verified=False,
        is_active=True,
        referral_code=referral_code,
    )
    db.add(user)
    await db.flush()  # get user.id before commit

    # Apply referral if a code was provided at signup
    if data.referral_code:
        from app.services.referral_service import apply_referral_on_register
        await apply_referral_on_register(db, user, data.referral_code)

    await _send_new_verification_code(db, user)
    return user


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

async def verify_email(db: AsyncSession, email: str, code: str) -> User:
    user = await _get_user_by_email(db, email)
    if not user:
        raise ValueError("User not found.")
    if user.is_verified:
        raise ValueError("Account is already verified.")

    vc = await _get_latest_unused_code(db, user.id)
    if not vc:
        raise ValueError("No verification code found. Please request a new one.")
    if _utc_now() > vc.expires_at.replace(tzinfo=timezone.utc):
        raise ValueError("Verification code has expired. Please request a new one.")
    if not verify_verification_code(code, vc.hashed_code):
        raise ValueError("Invalid verification code.")

    vc.used = True
    user.is_verified = True
    return user


async def resend_verification_code(db: AsyncSession, email: str) -> None:
    user = await _get_user_by_email(db, email)
    if not user:
        raise ValueError("User not found.")
    if user.is_verified:
        raise ValueError("Account is already verified.")
    await _send_new_verification_code(db, user)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def login_user(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    user = await _get_user_by_email(db, data.email)
    if not user:
        raise ValueError("Invalid email or password.")

    # Account lockout
    if user.locked_until and _utc_now() < user.locked_until.replace(tzinfo=timezone.utc):
        minutes_left = int((user.locked_until.replace(tzinfo=timezone.utc) - _utc_now()).total_seconds() / 60) + 1
        raise ValueError(f"Account temporarily locked. Try again in {minutes_left} minute(s).")

    if not verify_password(data.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_failed_login_attempts:
            user.locked_until = _utc_now() + timedelta(minutes=settings.account_lockout_minutes)
            logger.warning("Account locked for user %s after failed attempts", user.email)
            raise ValueError(
                f"Too many failed attempts. Account locked for {settings.account_lockout_minutes} minutes."
            )
        raise ValueError("Invalid email or password.")

    # Status checks after password is validated (avoids leaking account existence via error order)
    if not user.is_verified:
        await _send_new_verification_code(db, user)
        raise ValueError("UNVERIFIED_EMAIL")
    if user.is_suspended:
        raise ValueError("Your account has been suspended. Please contact support.")
    if not user.is_active:
        raise ValueError("Your account is inactive. Please contact support.")

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None

    access_token, access_jti, access_exp = create_access_token(str(user.id), user.role.value)
    refresh_token, refresh_jti, refresh_exp = create_refresh_token(str(user.id))

    await _store_refresh_jti(db, refresh_jti, refresh_exp)

    logger.info("User %s logged in", user.email)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


## ---------------------------------------------
## Password reset 
## ---------------------------------------------
async def request_password_reset(db: AsyncSession, email: str) -> None:
    """Send a reset code. Silently succeeds even if email doesn't exist (prevents enumeration)."""
    from app.models.password_reset_code import PasswordResetCode

    user = await _get_user_by_email(db, email)
    if not user:
        return  # silent — don't reveal whether email exists

    # Invalidate any existing unused codes
    existing = await db.execute(
        select(PasswordResetCode).where(
            PasswordResetCode.user_id == user.id,
            PasswordResetCode.used == False  # noqa: E712
        )
    )
    for code in existing.scalars().all():
        code.used = True

    plain_code = generate_verification_code()
    hashed = hash_verification_code(plain_code)
    reset_code = PasswordResetCode(
        user_id=user.id,
        hashed_code=hashed,
        expires_at=_utc_now() + timedelta(minutes=15),
    )
    db.add(reset_code)
    await db.flush()

    await email_service.send_notification_email(
        to_email=user.email,
        username=user.username,
        title="Reset Your Password",
        message=(
            f"Your password reset code is: <strong style='font-size:24px;letter-spacing:6px'>{plain_code}</strong><br><br>"
            "This code expires in <strong>15 minutes</strong>.<br>"
            "If you did not request a password reset, please ignore this email."
        ),
    )


async def reset_password(db: AsyncSession, email: str, code: str, new_password: str) -> None:
    from app.models.password_reset_code import PasswordResetCode

    user = await _get_user_by_email(db, email)
    if not user:
        raise ValueError("Invalid request.")

    result = await db.execute(
        select(PasswordResetCode)
        .where(PasswordResetCode.user_id == user.id, PasswordResetCode.used == False)  # noqa: E712
        .order_by(PasswordResetCode.created_at.desc())
        .limit(1)
    )
    reset_code = result.scalar_one_or_none()

    if not reset_code:
        raise ValueError("No reset code found. Please request a new one.")
    if _utc_now() > reset_code.expires_at.replace(tzinfo=timezone.utc):
        raise ValueError("Reset code has expired. Please request a new one.")
    if not verify_verification_code(code, reset_code.hashed_code):
        raise ValueError("Invalid reset code.")

    if not validate_password_strength(new_password):
        raise ValueError(get_password_policy_message())

    reset_code.used = True
    user.hashed_password = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------

async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise ValueError("Invalid or expired refresh token.")

    if payload.get("type") != "refresh":
        raise ValueError("Invalid token type.")

    jti = payload.get("jti")
    if not jti:
        raise ValueError("Malformed token.")

    if await _is_token_blacklisted(db, jti):
        raise ValueError("Refresh token has been revoked.")

    user_id = payload.get("sub")
    user = await db.get(User, int(user_id))
    if not user or not user.is_active or user.is_suspended:
        raise ValueError("User not found or account inactive.")

    # Blacklist old refresh token (rotation)
    await _blacklist_token(db, jti, datetime.fromtimestamp(payload["exp"], tz=timezone.utc))

    access_token, _, _ = create_access_token(str(user.id), user.role.value)
    new_refresh_token, new_refresh_jti, new_refresh_exp = create_refresh_token(str(user.id))
    await _store_refresh_jti(db, new_refresh_jti, new_refresh_exp)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

async def logout_user(db: AsyncSession, access_jti: str, access_exp: datetime, refresh_token: str | None) -> None:
    await _blacklist_token(db, access_jti, access_exp)

    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") == "refresh":
                jti = payload.get("jti")
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                if jti:
                    await _blacklist_token(db, jti, exp)
        except JWTError:
            pass


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def _email_exists(db: AsyncSession, email: str) -> bool:
    result = await db.execute(select(User.id).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none() is not None


async def _username_exists(db: AsyncSession, username: str) -> bool:
    result = await db.execute(select(User.id).where(User.username == username.strip()))
    return result.scalar_one_or_none() is not None


async def _phone_exists(db: AsyncSession, phone: str) -> bool:
    result = await db.execute(select(User.id).where(User.phone_number == phone.strip()))
    return result.scalar_one_or_none() is not None


async def _get_latest_unused_code(db: AsyncSession, user_id: int) -> VerificationCode | None:
    result = await db.execute(
        select(VerificationCode)
        .where(VerificationCode.user_id == user_id, VerificationCode.used == False)  # noqa: E712
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _send_new_verification_code(db: AsyncSession, user: User) -> None:
    existing = await db.execute(
        select(VerificationCode).where(
            VerificationCode.user_id == user.id, VerificationCode.used == False  # noqa: E712
        )
    )
    for code in existing.scalars().all():
        code.used = True

    plain_code = generate_verification_code()
    hashed = hash_verification_code(plain_code)
    vc = VerificationCode(
        user_id=user.id,
        hashed_code=hashed,
        expires_at=_utc_now() + timedelta(minutes=10),
    )
    db.add(vc)
    await db.flush()

    sent = await email_service.send_verification_email(user.email, user.username, plain_code)
    if not sent:
        logger.error("Verification email failed for user %s", user.email)


async def _blacklist_token(db: AsyncSession, jti: str, expires_at: datetime) -> None:
    entry = BlacklistedToken(jti=jti, expires_at=expires_at)
    db.add(entry)


async def _store_refresh_jti(db: AsyncSession, jti: str, expires_at: datetime) -> None:
    pass  # JTI is checked at refresh time; blacklisting happens on rotation/logout


async def _is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    result = await db.execute(select(BlacklistedToken.id).where(BlacklistedToken.jti == jti))
    return result.scalar_one_or_none() is not None
