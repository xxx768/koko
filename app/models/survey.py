from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.user import User


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reward_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0.00, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    questions: Mapped[list["SurveyQuestion"]] = relationship(
        "SurveyQuestion", back_populates="survey", cascade="all, delete-orphan"
    )
    submissions: Mapped[list["SurveySubmission"]] = relationship(
        "SurveySubmission", back_populates="survey", cascade="all, delete-orphan"
    )


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    survey: Mapped[Survey] = relationship("Survey", back_populates="questions")
    options: Mapped[list["SurveyOption"]] = relationship(
        "SurveyOption", back_populates="question", cascade="all, delete-orphan"
    )
    answers: Mapped[list["SurveyAnswer"]] = relationship(
        "SurveyAnswer", back_populates="question", cascade="all, delete-orphan"
    )


class SurveyOption(Base):
    __tablename__ = "survey_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("survey_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    question: Mapped[SurveyQuestion] = relationship("SurveyQuestion", back_populates="options")
    answers: Mapped[list["SurveyAnswer"]] = relationship(
        "SurveyAnswer", back_populates="option", cascade="all, delete-orphan"
    )


class SurveySubmission(Base):
    __tablename__ = "survey_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped[User] = relationship("User")
    survey: Mapped[Survey] = relationship("Survey", back_populates="submissions")
    answers: Mapped[list["SurveyAnswer"]] = relationship(
        "SurveyAnswer", back_populates="submission", cascade="all, delete-orphan"
    )


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("survey_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("survey_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("survey_options.id", ondelete="CASCADE"), nullable=False, index=True)

    submission: Mapped[SurveySubmission] = relationship("SurveySubmission", back_populates="answers")
    question: Mapped[SurveyQuestion] = relationship("SurveyQuestion", back_populates="answers")
    option: Mapped[SurveyOption] = relationship("SurveyOption", back_populates="answers")
