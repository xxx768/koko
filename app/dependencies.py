from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.blacklisted_token import BlacklistedToken
from app.models.user import User, UserRole
from app.services.jwt_service import decode_token

_bearer = HTTPBearer(auto_error=True)


async def _get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, str, datetime]:
    """Validate access token and return (user, jti, exp)."""
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

    # Check blacklist
    result = await db.execute(select(BlacklistedToken.id).where(BlacklistedToken.jti == jti))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")
    if user.is_suspended:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended.")

    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    return user, jti, exp


async def get_current_user(
    result: tuple = Depends(_get_current_user_from_token),
) -> User:
    user, _, _ = result
    return user


async def get_current_user_with_token_meta(
    result: tuple = Depends(_get_current_user_from_token),
) -> tuple[User, str, datetime]:
    return result


def require_role(*roles: UserRole):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return user

    return _check


require_admin = require_role(UserRole.admin)
require_user = require_role(UserRole.user, UserRole.admin)
