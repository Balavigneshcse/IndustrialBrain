"""Liveness and readiness probes (no authentication)."""
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ...core.config import get_settings
from ...db.session import get_sessionmaker
from ...schemas.common import HealthCheck, HealthLegacy, HealthReady

router = APIRouter(prefix="/health", tags=["health"])
VERSION = "3.0.0"


@router.get("", response_model=HealthLegacy)
async def health() -> HealthLegacy:
    return HealthLegacy(status="ok", service="indusmind-ai", version=VERSION)


@router.get("/live", response_model=HealthLegacy)
async def live() -> HealthLegacy:
    """The process is up. Does not touch dependencies."""
    return HealthLegacy(status="ok", service="indusmind-ai", version=VERSION)


@router.get("/ready", response_model=HealthReady, responses={503: {"model": HealthReady}})
async def ready():
    """Dependencies are usable: database with pgvector, writable upload folder. 503 if not."""
    checks: dict[str, HealthCheck] = {}
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
            has_vector = (await session.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'"))).scalar_one()
        checks["database"] = HealthCheck(status="ok")
        checks["pgvector"] = HealthCheck(status="ok" if has_vector else "error",
                                         detail=None if has_vector else "extension not installed; run migrations")
    except Exception as exc:  # report, don't crash the probe
        checks["database"] = HealthCheck(status="error", detail=type(exc).__name__)
    upload_path = get_settings().upload_path
    writable = upload_path.is_dir() and os.access(upload_path, os.W_OK)
    checks["uploads"] = HealthCheck(status="ok" if writable else "error",
                                    detail=None if writable else f"{upload_path} is not writable")
    healthy = all(c.status == "ok" for c in checks.values())
    body = HealthReady(status="ok" if healthy else "degraded", checks=checks)
    return JSONResponse(body.model_dump(), status_code=200 if healthy else 503)
