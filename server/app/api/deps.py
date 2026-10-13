"""Request dependencies: database session, current user, role checks."""
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_access_token, password_version
from ..db.models import User
from ..db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login or /auth/refresh")
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(401, "Not authenticated", headers=_CHALLENGE)
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Invalid or expired token", headers=_CHALLENGE)
    user = await session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(401, "Account not found or disabled", headers=_CHALLENGE)
    # Tokens issued before the last password change (or reset) are no longer valid.
    if payload.get("pwv") != password_version(user.password_changed_at):
        raise HTTPException(401, "Session ended by a password change; sign in again", headers=_CHALLENGE)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"This action requires the {' or '.join(roles)} role")
        return user
    return dependency


EngineerUser = Annotated[User, Depends(require_roles("admin", "engineer"))]
AdminUser = Annotated[User, Depends(require_roles("admin"))]
