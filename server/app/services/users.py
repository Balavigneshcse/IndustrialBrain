"""User helpers shared by the auth and user-management routes and the CLI."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.security import hash_password
from ..db.models import RefreshToken, User
from ..schemas.auth import UserOut


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, displayName=user.display_name, email=user.email,
                   role=user.role, isActive=user.is_active, lastLoginAt=user.last_login_at,
                   createdAt=user.created_at)


def password_problem(password: str, username: str) -> str | None:
    minimum = get_settings().min_password_length
    if len(password) < minimum:
        return f"Password must be at least {minimum} characters"
    if password.lower() == username.lower():
        return "Password must not be the same as the username"
    if len(set(password)) < 4:
        return "Password is too simple"
    return None


def validate_password(password: str, username: str) -> None:
    message = password_problem(password, username)
    if message:
        raise HTTPException(422, message)


async def create_user(session: AsyncSession, username: str, display_name: str, role: str, password: str,
                      email: str | None = None) -> User:
    user = User(username=username, display_name=display_name, role=role, email=email,
                password_hash=hash_password(password))
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def revoke_all_sessions(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def other_active_admins(session: AsyncSession, excluding_user_id: int) -> int:
    return (await session.execute(
        select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True), User.id != excluding_user_id)
    )).scalar_one()
