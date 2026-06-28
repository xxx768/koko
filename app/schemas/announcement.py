from datetime import datetime
from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)


class AnnouncementResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    message: str
    is_active: bool
    created_at: datetime