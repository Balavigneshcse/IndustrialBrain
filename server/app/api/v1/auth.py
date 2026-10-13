"""Sign-in with short-lived access tokens and rotating, httpOnly refresh-token cookies."""
import math
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from sqlalchemy import select

from ...core.config import get_settings
from ...core.ratelimit import limiter
from ...core.security import (create_access_token, hash_password, hash_token, new_refresh_token,
                              password_needs_rehash, password_version, verify_password)
from ...db.models import RefreshToken, User
from ...schemas.auth import LoginRequest, PasswordChange, TokenResponse, UserOut
from ...schemas.common import ERROR_RESPONSES, Problem
from ...services import audit
from ...services.users import revoke_all_sessions, user_out, validate_password
from ..deps import CurrentUser, SessionDep

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "indusmind_refresh"
COOKIE_PATH = "/api"  # covers both /api/v1/auth and the legacy /api/auth alias
REUSE_GRACE = timedelta(seconds=10)  # two tabs refreshing at once is not treated as theft


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _issue_tokens(session: SessionDep, user: User, request: Request, response: Response) -> tuple[TokenResponse, RefreshToken]:
    settings = get_settings()
    raw, digest = new_refresh_token()
    row = RefreshToken(
        user_id=user.id, token_hash=digest, expires_at=_now() + timedelta(days=settings.refresh_token_days),
        user_agent=(request.headers.get("user-agent") or "")[:256], ip=audit.client_ip(request),
    )
    session.add(row)
    await session.flush()
    response.set_cookie(
        REFRESH_COOKIE, raw, max_age=settings.refresh_token_days * 86400, httponly=True,
        secure=settings.cookie_secure, samesite="strict", path=COOKIE_PATH,
    )
    access, expires_in = create_access_token(user.id, user.username, user.role, password_version(user.password_changed_at))
    return TokenResponse(token=access, expiresIn=expires_in, username=user.username,
                         displayName=user.display_name, role=user.role), row


@router.post("/login", response_model=TokenResponse, responses={
    401: {"model": Problem, "description": "Wrong username or password"},
    423: {"model": Problem, "description": "Account temporarily locked after repeated failures"},
    429: ERROR_RESPONSES[429]})
async def login(body: LoginRequest, request: Request, response: Response, session: SessionDep) -> TokenResponse:
    settings = get_settings()
    limiter.check(f"login:{audit.client_ip(request)}", settings.login_rate_per_minute)
    user = (await session.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    now = _now()

    if user is not None and user.locked_until is not None and user.locked_until > now:
        minutes = math.ceil((user.locked_until - now).total_seconds() / 60)
        raise HTTPException(423, f"Account locked after repeated failed sign-ins. Try again in {minutes} minute(s).")

    password_ok = verify_password(user.password_hash if user else None, body.password)
    if user is None or not password_ok or not user.is_active:
        if user is not None and not password_ok:
            user.failed_logins += 1
            if user.failed_logins >= settings.max_failed_logins:
                user.failed_logins = 0
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                audit.record(session, "account_locked", user=user, request=request)
        audit.record(session, "login_failed", user=user, username=body.username[:64], request=request)
        await session.commit()
        raise HTTPException(401, "Incorrect username or password")

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    tokens, _ = await _issue_tokens(session, user, request, response)
    audit.record(session, "login", user=user, request=request)
    await session.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse, responses={401: {"model": Problem}})
async def refresh(request: Request, response: Response, session: SessionDep,
                  indusmind_refresh: Annotated[str | None, Cookie()] = None) -> TokenResponse:
    """Exchange the refresh cookie for a new access token; the refresh token rotates every time."""
    if not indusmind_refresh:
        raise HTTPException(401, "No session; sign in again")
    row = (await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(indusmind_refresh)).with_for_update()
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(401, "Session expired; sign in again")
    now = _now()
    user = await session.get(User, row.user_id)

    if row.revoked_at is not None:
        if now - row.revoked_at > REUSE_GRACE:
            # A rotated token was presented again: assume it was stolen and end every session.
            await revoke_all_sessions(session, row.user_id)
            audit.record(session, "refresh_token_reuse", user=user, request=request)
            await session.commit()
        raise HTTPException(401, "Session expired; sign in again")
    if row.expires_at <= now or user is None or not user.is_active:
        raise HTTPException(401, "Session expired; sign in again")

    tokens, new_row = await _issue_tokens(session, user, request, response)
    row.revoked_at = now
    row.replaced_by_id = new_row.id
    await session.commit()
    return tokens


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session: SessionDep,
                 indusmind_refresh: Annotated[str | None, Cookie()] = None) -> None:
    if indusmind_refresh:
        row = (await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(indusmind_refresh))
        )).scalar_one_or_none()
        if row is not None and row.revoked_at is None:
            row.revoked_at = _now()
            audit.record(session, "logout", user=await session.get(User, row.user_id), request=request)
            await session.commit()
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=UserOut, responses={401: ERROR_RESPONSES[401]})
async def me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.post("/change-password", response_model=TokenResponse, responses={
    400: {"model": Problem, "description": "Current password is wrong"}, 401: ERROR_RESPONSES[401],
    422: {"model": Problem, "description": "New password does not meet the policy"}})
async def change_password(body: PasswordChange, request: Request, response: Response,
                          session: SessionDep, user: CurrentUser) -> TokenResponse:
    """Change your own password. Ends all other sessions and returns fresh tokens for this one."""
    if not verify_password(user.password_hash, body.currentPassword):
        raise HTTPException(400, "Current password is incorrect")
    validate_password(body.newPassword, user.username)
    user.password_hash = hash_password(body.newPassword)
    user.password_changed_at = _now()
    await revoke_all_sessions(session, user.id)
    tokens, _ = await _issue_tokens(session, user, request, response)
    audit.record(session, "password_changed", user=user, request=request)
    await session.commit()
    return tokens


