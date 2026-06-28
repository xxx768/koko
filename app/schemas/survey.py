from datetime import datetime

from pydantic import BaseModel, Field


class SurveyOptionInput(BaseModel):
    label: str = Field(..., min_length=1, max_length=500)


class SurveyQuestionInput(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)
    options: list[SurveyOptionInput] = Field(..., min_length=2, max_length=6)


class SurveyCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    reward_amount: float = Field(..., ge=0)
    questions: list[SurveyQuestionInput] = Field(..., min_length=1, max_length=5)


class SurveyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    description: str | None
    reward_amount: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
    questions: list["SurveyQuestionResponse"]


class SurveyQuestionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    prompt: str
    order: int
    options: list["SurveyOptionResponse"]


class SurveyOptionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    label: str
    order: int


class SurveySubmissionRequest(BaseModel):
    answers: list[dict[str, int]]


class SurveySubmissionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    survey_id: int
    submitted_at: datetime
