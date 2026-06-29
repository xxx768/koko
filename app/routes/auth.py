import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import get_current_user_with_token_meta
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResendCodeRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.services import auth_service
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest

# from slowapi import Limiter
# from slowapi.util import get_remote_address

# limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account. Sends a 5-digit verification code by email."""
    try:
        user = await auth_service.register_user(db, data)
        return {
            "message": "Registration successful. Please check your email for the verification code.",
            "email": user.email,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Verify email with the 5-digit code sent during registration."""
    try:
        await auth_service.verify_email(db, data.email, data.code)
        return {"message": "Email verified successfully. You can now log in."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/resend-code", status_code=status.HTTP_200_OK)
async def resend_code(data: ResendCodeRequest, db: AsyncSession = Depends(get_db)):
    """Resend the email verification code."""
    try:
        await auth_service.resend_verification_code(db, data.email)
        return {"message": "A new verification code has been sent to your email."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password. Returns JWT access and refresh tokens."""
    try:
        return await auth_service.login_user(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
# @limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Send a 5-digit password reset code to the user's email."""
    await auth_service.request_password_reset(db, data.email)
    return {"message": "If an account with that email exists, a reset code has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
# @limiter.limit("5/minute")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using the emailed code."""
    try:
        await auth_service.reset_password(db, data.email, data.code, data.new_password)
        return {"message": "Password reset successfully. You can now log in."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/refresh-token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Get a new access token using a valid refresh token (token rotation)."""
    try:
        return await auth_service.refresh_access_token(db, data.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    data: LogoutRequest,
    token_meta: tuple = Depends(get_current_user_with_token_meta),
    db: AsyncSession = Depends(get_db),
):
    """Logout and blacklist both the access and refresh tokens."""
    user, jti, exp = token_meta
    await auth_service.logout_user(db, jti, exp, data.refresh_token)
    logger.info("User %s logged out", user.email)
    return {"message": "Logged out successfully."}
