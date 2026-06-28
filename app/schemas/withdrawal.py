


from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.withdrawal import WithdrawalStatus


# ---------------------------------------------------------------------------
# User-facing
# ---------------------------------------------------------------------------

class WithdrawalCreateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    bank_name: str = Field(..., min_length=2, max_length=100)
    account_number: str = Field(..., min_length=4, max_length=34)
    account_name: str = Field(..., min_length=2, max_length=100)

    @field_validator("bank_name", "account_number", "account_name")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class WithdrawalResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    amount: Decimal
    bank_name: str
    account_number: str
    account_name: str
    fee_amount: Decimal
    status: WithdrawalStatus
    # True when a proof image is currently stored; the raw b64 is never sent to users.
    has_proof_image: bool = False
    proof_uploaded_at: datetime | None
    admin_note: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_orm_with_flags(cls, obj: object) -> "WithdrawalResponse":
        """
        Construct from an ORM instance, computing the `has_proof_image` flag
        without exposing the raw base64 data.
        """
        data = {
            "id": obj.id,
            "amount": obj.amount,
            "bank_name": obj.bank_name,
            "account_number": obj.account_number,
            "account_name": obj.account_name,
            "fee_amount": obj.fee_amount,
            "status": obj.status,
            "has_proof_image": bool(obj.proof_image_b64),
            "proof_uploaded_at": obj.proof_uploaded_at,
            "admin_note": obj.admin_note,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
            "completed_at": obj.completed_at,
        }
        return cls.model_validate(data)


class WithdrawalFeeInfoResponse(BaseModel):
    """What the user needs in order to pay the withdrawal fee."""

    fee_amount: Decimal
    fee_bank_name: str
    fee_account_number: str
    fee_account_name: str


# ---------------------------------------------------------------------------
# Admin-facing
# ---------------------------------------------------------------------------

class WithdrawalSettingResponse(BaseModel):
    model_config = {"from_attributes": True}

    min_balance: Decimal
    fee_amount: Decimal
    fee_bank_name: str
    fee_account_number: str
    fee_account_name: str
    daily_withdrawal_limit: int = Field(..., ge=1)



class WithdrawalSettingUpdateRequest(BaseModel):
    min_balance: Decimal = Field(..., ge=0)
    fee_amount: Decimal = Field(..., ge=0)
    fee_bank_name: str = Field(..., min_length=2, max_length=100)
    fee_account_number: str = Field(..., min_length=4, max_length=34)
    fee_account_name: str = Field(..., min_length=2, max_length=100)
    daily_withdrawal_limit: int = Field(..., ge=1)


    @field_validator("fee_bank_name", "fee_account_number", "fee_account_name")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class WithdrawalRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class WithdrawalListParams(BaseModel):
    status: WithdrawalStatus | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# Admin response that includes the data-URI so the admin UI can render the image.
# Never sent to regular users.
class WithdrawalAdminDetailResponse(WithdrawalResponse):
    """
    Extends the regular response with the raw proof image data-URI.
    Only returned by admin endpoints.
    """
    proof_image_data_uri: str | None = None