"""Password hashing (Argon2id), access tokens (JWT) and refresh tokens (opaque, stored hashed)."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import get_settings

_hasher = PasswordHasher()  # Argon2id with the library's recommended parameters
# Verified against when the username does not exist, so response time does not reveal it.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_version(password_changed_at: datetime) -> int:
    """Changes whenever the password is changed or reset; tokens carrying an older value are rejected."""
    return int(password_changed_at.timestamp() * 1000)


def create_access_token(user_id: int, username: str, role: str, pwv: int) -> tuple[str, int]:
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id), "username": username, "role": role, "type": "access", "pwv": pwv,
        "iat": now, "exp": now + lifetime, "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key.get_secret_value(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == "access" else None


def new_refresh_token() -> tuple[str, str]:
    """Return (raw token for the cookie, SHA-256 hash for the database)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
