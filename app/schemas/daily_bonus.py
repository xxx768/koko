from pydantic import BaseModel, Field


class DailyBonusSettingRequest(BaseModel):
    amount: float = Field(..., ge=0)


class DailyBonusStatusResponse(BaseModel):
    can_claim: bool
    next_claim_at: str | None = None
    bonus_amount: float
    last_claimed_at: str | None = None
