from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    email: EmailStr
    phone_number: str
    role: UserRole
    balance: Decimal
    is_verified: bool
    is_active: bool
    is_suspended: bool
    created_at: datetime
    updated_at: datetime


class UserUpdateRequest(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    phone_number: str | None = Field(None, min_length=7, max_length=20, pattern=r"^\+?[0-9\s\-]+$")


class NotificationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime
