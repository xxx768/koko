from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.auth import RegisterRequest


class AdminCreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    phone_number: str = Field(..., min_length=7, max_length=20, pattern=r"^\+?[0-9\s\-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.user


class AdminUpdateUserRequest(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr | None = None
    phone_number: str | None = Field(None, min_length=7, max_length=20, pattern=r"^\+?[0-9\s\-]+$")
    role: UserRole | None = None
    balance: float | None = Field(None, ge=0)


class AdminNotifyUserRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)
    send_email: bool = False


class UserSearchParams(BaseModel):
    search: str | None = None
    role: UserRole | None = None
    is_suspended: bool | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
