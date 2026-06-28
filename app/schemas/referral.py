from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ReferralSettingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    reward_amount: Decimal
    is_enabled: bool
    updated_at: datetime


class ReferralSettingUpdateRequest(BaseModel):
    reward_amount: Decimal = Field(..., ge=0, decimal_places=2)
    is_enabled: bool = True


class ReferralStatsResponse(BaseModel):
    referral_code: str
    total_referrals: int
    paid_referrals: int
    pending_referrals: int
    total_earned: Decimal
