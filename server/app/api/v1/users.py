"""User and role management (admin only)."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from ...core.security import hash_password
from ...db.models import User
from ...schemas.auth import PasswordReset, UserCreate, UserOut, UserUpdate
from ...schemas.common import ERROR_RESPONSES, Ok, Problem
from ...services import audit
from ...services.users import create_user, other_active_admins, revoke_all_sessions, user_out, validate_password
from ..deps import AdminUser, SessionDep

router = APIRouter(prefix="/users", tags=["users"], responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]})


async def _get_user(session: SessionDep, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.get("", response_model=list[UserOut])
async def list_users(session: SessionDep, _: AdminUser) -> list[UserOut]:
    users = (await session.execute(select(User).order_by(User.username))).scalars()
    return [user_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=201,
             responses={409: {"model": Problem, "description": "Username already taken"}, 422: {"model": Problem}})
async def add_user(body: UserCreate, request: Request, session: SessionDep, admin: AdminUser) -> UserOut:
    if (await session.execute(select(User.id).where(User.username == body.username))).first():
        raise HTTPException(409, f"Username '{body.username}' is already taken")
    validate_password(body.password, body.username)
    user = await create_user(session, body.username, body.displayName, body.role, body.password, body.email)
    audit.record(session, "user_created", user=admin, request=request, target_type="user", target_id=user.id,
                 detail={"username": user.username, "role": user.role})
    await session.commit()
    return user_out(user)


@router.patch("/{user_id}", response_model=UserOut,
              responses={404: {"model": Problem}, 409: {"model": Problem, "description": "Would remove the last active admin"}})
async def update_user(user_id: int, body: UserUpdate, request: Request, session: SessionDep, admin: AdminUser) -> UserOut:
    user = await _get_user(session, user_id)
    changes = body.model_dump(exclude_unset=True)
    loses_admin = user.role == "admin" and (changes.get("role", "admin") != "admin" or changes.get("isActive") is False)
    if loses_admin and await other_active_admins(session, user.id) == 0:
        raise HTTPException(409, "Cannot remove or disable the last active admin")

    if "displayName" in changes:
        user.display_name = changes["displayName"]
    if "email" in changes:
        user.email = changes["email"]
    if "role" in changes:
        user.role = changes["role"]
    if "isActive" in changes:
        user.is_active = changes["isActive"]
        if not user.is_active:
            await revoke_all_sessions(session, user.id)
    audit.record(session, "user_updated", user=admin, request=request, target_type="user", target_id=user.id,
                 detail=changes)
    await session.commit()
    await session.refresh(user)
    return user_out(user)


@router.post("/{user_id}/reset-password", response_model=Ok, responses={404: {"model": Problem}, 422: {"model": Problem}})
async def reset_password(user_id: int, body: PasswordReset, request: Request, session: SessionDep, admin: AdminUser) -> Ok:
    """Set a new password, unlock the account and end all of the user's sessions."""
    user = await _get_user(session, user_id)
    validate_password(body.newPassword, user.username)
    user.password_hash = hash_password(body.newPassword)
    user.password_changed_at = datetime.now(timezone.utc)
    user.failed_logins = 0
    user.locked_until = None
    await revoke_all_sessions(session, user.id)
    audit.record(session, "password_reset", user=admin, request=request, target_type="user", target_id=user.id)
    await session.commit()
    return Ok()
