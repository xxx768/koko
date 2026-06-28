from datetime import datetime, timezone

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.survey import Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveySubmission
from app.models.user import User
from app.schemas.survey import SurveyCreateRequest, SurveySubmissionRequest


async def list_active_surveys(db: AsyncSession) -> list[Survey]:
    result = await db.execute(
        select(Survey)
        .options(selectinload(Survey.questions).selectinload(SurveyQuestion.options))
        .where(Survey.is_active == True)
        .order_by(Survey.created_at.desc())
    )
    return list(result.scalars().all())


async def list_active_surveys_for_user(db: AsyncSession, user: User) -> list[Survey]:
    subquery = select(SurveySubmission.id).where(
        SurveySubmission.survey_id == Survey.id,
        SurveySubmission.user_id == user.id,
    )

    result = await db.execute(
        select(Survey)
        .options(selectinload(Survey.questions).selectinload(SurveyQuestion.options))
        .where(Survey.is_active == True)
        .where(~exists(subquery))
        .order_by(Survey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_survey(db: AsyncSession, survey_id: int) -> Survey:
    result = await db.execute(
        select(Survey)
        .options(selectinload(Survey.questions).selectinload(SurveyQuestion.options))
        .where(Survey.id == survey_id, Survey.is_active == True)
    )
    survey = result.scalar_one_or_none()
    if not survey:
        raise ValueError("Survey not found.")
    return survey


async def create_survey(db: AsyncSession, data: SurveyCreateRequest) -> Survey:
    survey = Survey(
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        reward_amount=data.reward_amount,
        is_active=True,
    )
    db.add(survey)
    await db.flush()

    for index, question_data in enumerate(data.questions, start=1):
        question = SurveyQuestion(survey_id=survey.id, prompt=question_data.prompt.strip(), order=index)
        db.add(question)
        await db.flush()
        for option_index, option_data in enumerate(question_data.options, start=1):
            option = SurveyOption(question_id=question.id, label=option_data.label.strip(), order=option_index)
            db.add(option)
    await db.flush()

    return await get_survey(db, survey.id)


async def delete_survey(db: AsyncSession, survey_id: int) -> None:
    survey = await db.get(Survey, survey_id)
    if not survey:
        raise ValueError("Survey not found.")
    await db.delete(survey)


async def submit_survey(db: AsyncSession, survey: Survey, user: User, data: SurveySubmissionRequest) -> SurveySubmission:
    existing = (
        await db.execute(
            select(SurveySubmission).where(SurveySubmission.user_id == user.id, SurveySubmission.survey_id == survey.id)
        )
    ).scalar_one_or_none()
    if existing:
        raise ValueError("You have already submitted this survey.")

    submission = SurveySubmission(user_id=user.id, survey_id=survey.id)
    db.add(submission)
    await db.flush()

    for answer in data.answers:
        question_id = answer.get("question_id")
        option_id = answer.get("option_id")
        if question_id is None or option_id is None:
            continue
        db.add(SurveyAnswer(submission_id=submission.id, question_id=question_id, option_id=option_id))

    user.balance = float(user.balance) + float(survey.reward_amount)
    return submission