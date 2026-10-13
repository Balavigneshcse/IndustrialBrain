from typing import Literal

from pydantic import BaseModel


class Ok(BaseModel):
    ok: bool = True


class Problem(BaseModel):
    """RFC 7807 error body returned for every 4xx/5xx response."""
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    requestId: str | None = None


class HealthLegacy(BaseModel):
    status: str
    service: str
    version: str


class HealthCheck(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None


class HealthReady(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, HealthCheck]


ERROR_RESPONSES = {
    401: {"model": Problem, "description": "Missing, invalid or expired access token"},
    403: {"model": Problem, "description": "Authenticated but not allowed (role)"},
    429: {"model": Problem, "description": "Rate limit exceeded; see Retry-After"},
}
