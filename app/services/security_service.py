import re
import secrets

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# Argon2 via pwdlib — bcrypt is explicitly forbidden per spec
_hasher = PasswordHash([Argon2Hasher()])


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using Argon2."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its Argon2 hash."""
    try:
        return _hasher.verify(plain_password, hashed_password)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------

_PASSWORD_POLICY = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]).{8,}$"
)


def validate_password_strength(password: str) -> bool:
    """Return True if password meets the security policy."""
    return bool(_PASSWORD_POLICY.match(password))


def get_password_policy_message() -> str:
    return (
        "Password must be at least 8 characters and include "
        "uppercase, lowercase, a number, and a special character."
    )


# ---------------------------------------------------------------------------
# Verification code generation & hashing
# ---------------------------------------------------------------------------

def generate_verification_code() -> str:
    """Generate a cryptographically secure 5-digit numeric code."""
    return "".join([str(secrets.randbelow(10)) for _ in range(5)])


def hash_verification_code(code: str) -> str:
    """Hash a verification code the same way as a password (Argon2)."""
    return _hasher.hash(code)


def verify_verification_code(plain_code: str, hashed_code: str) -> bool:
    """Verify a plain verification code against its hash."""
    try:
        return _hasher.verify(plain_code, hashed_code)
    except Exception:
        return False
