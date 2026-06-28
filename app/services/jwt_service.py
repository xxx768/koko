import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, role: str) -> tuple[str, str, datetime]:
    """Create a JWT access token. Returns (token, jti, expires_at)."""
    jti = str(uuid.uuid4())
    expires_at = _utc_now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "jti": jti,
        "type": "access",
        "exp": expires_at,
        "iat": _utc_now(),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """Create a JWT refresh token. Returns (token, jti, expires_at)."""
    jti = str(uuid.uuid4())
    expires_at = _utc_now() + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": subject,
        "jti": jti,
        "type": "refresh",
        "exp": expires_at,
        "iat": _utc_now(),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise exc
