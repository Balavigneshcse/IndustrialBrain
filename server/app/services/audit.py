"""Audit trail for security-relevant actions (logins, uploads, deletions, exports, user changes)."""
import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuditLog, User

log = structlog.get_logger("audit")


def client_ip(request: Request | None) -> str | None:
    return request.client.host if request is not None and request.client else None


def record(session: AsyncSession, action: str, *, user: User | None = None, username: str | None = None,
           request: Request | None = None, target_type: str | None = None, target_id: str | int | None = None,
           detail: dict | None = None) -> None:
    """Add an audit entry to the session; it is committed with the caller's transaction."""
    entry = AuditLog(
        user_id=user.id if user else None, username=username or (user.username if user else None),
        action=action, target_type=target_type, target_id=str(target_id) if target_id is not None else None,
        detail=detail or {}, ip=client_ip(request),
    )
    session.add(entry)
    log.info(action, username=entry.username, target_type=target_type, target_id=entry.target_id)
