from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.admin import AdminCreateUserRequest, AdminUpdateUserRequest, UserSearchParams
from app.services.security_service import (
    hash_password,
    validate_password_strength,
    get_password_policy_message,
)


async def list_users(db: AsyncSession, params: UserSearchParams) -> tuple[list[User], int]:
    query = select(User)

    if params.search:
        term = f"%{params.search}%"
        query = query.where(
            or_(
                User.username.ilike(term),
                User.email.ilike(term),
                User.phone_number.ilike(term),
            )
        )
    if params.role is not None:
        query = query.where(User.role == params.role)
    if params.is_suspended is not None:
        query = query.where(User.is_suspended == params.is_suspended)

    count_result = await db.execute(select(User.id).filter(query.whereclause))  # type: ignore[arg-type]
    total = len(count_result.all())

    query = query.offset((params.page - 1) * params.page_size).limit(params.page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise ValueError("User not found.")
    return user


async def create_user(db: AsyncSession, data: AdminCreateUserRequest) -> User:
    if not validate_password_strength(data.password):
        raise ValueError(get_password_policy_message())

    from sqlalchemy import select

    if (await db.execute(select(User.id).where(User.email == data.email.lower()))).scalar_one_or_none():
        raise ValueError("Email already in use.")
    if (await db.execute(select(User.id).where(User.username == data.username))).scalar_one_or_none():
        raise ValueError("Username already taken.")
    if (await db.execute(select(User.id).where(User.phone_number == data.phone_number))).scalar_one_or_none():
        raise ValueError("Phone number already in use.")

    user = User(
        username=data.username.strip(),
        email=data.email.lower().strip(),
        phone_number=data.phone_number.strip(),
        hashed_password=hash_password(data.password),
        role=data.role,
        is_verified=True,  # Admin-created users are pre-verified
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def update_user(db: AsyncSession, user_id: int, data: AdminUpdateUserRequest) -> User:
    user = await get_user(db, user_id)

    if data.username is not None:
        existing = (await db.execute(select(User.id).where(User.username == data.username, User.id != user_id))).scalar_one_or_none()
        if existing:
            raise ValueError("Username already taken.")
        user.username = data.username.strip()

    if data.email is not None:
        existing = (await db.execute(select(User.id).where(User.email == data.email.lower(), User.id != user_id))).scalar_one_or_none()
        if existing:
            raise ValueError("Email already in use.")
        user.email = data.email.lower().strip()

    if data.phone_number is not None:
        existing = (await db.execute(select(User.id).where(User.phone_number == data.phone_number, User.id != user_id))).scalar_one_or_none()
        if existing:
            raise ValueError("Phone number already in use.")
        user.phone_number = data.phone_number.strip()

    if data.role is not None:
        user.role = data.role

    if data.balance is not None:
        user.balance = data.balance

    return user


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await get_user(db, user_id)
    await db.delete(user)


async def suspend_user(db: AsyncSession, user_id: int) -> User:
    user = await get_user(db, user_id)
    if user.is_suspended:
        raise ValueError("User is already suspended.")
    user.is_suspended = True
    return user


async def activate_user(db: AsyncSession, user_id: int) -> User:
    user = await get_user(db, user_id)
    if not user.is_suspended:
        raise ValueError("User is not suspended.")
    user.is_suspended = False
    return user
