"""Liveness and readiness probes (no authentication)."""
import os
import time

from anyio import to_thread
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ...core.config import get_settings
from ...db.session import get_sessionmaker
from ...llm.client import get_llm
from ...schemas.common import HealthCheck, HealthLegacy, HealthReady
from ...services.models import models_ready
from ...workers.celery_app import HEARTBEAT_KEY

router = APIRouter(prefix="/health", tags=["health"])
VERSION = "3.0.0"
# Without these the API still works, in a reduced mode: status "degraded", but HTTP 200.
OPTIONAL_CHECKS = {"llm"}


@router.get("", response_model=HealthLegacy)
async def health() -> HealthLegacy:
    return HealthLegacy(status="ok", service="indusmind-ai", version=VERSION)


@router.get("/live", response_model=HealthLegacy)
async def live() -> HealthLegacy:
    """The process is up. Does not touch dependencies."""
    return HealthLegacy(status="ok", service="indusmind-ai", version=VERSION)


@router.get("/ready", response_model=HealthReady, responses={503: {"model": HealthReady}})
async def ready():
    """Dependencies are usable: database with pgvector, uploads, retrieval models, (when REDIS_URL is set)
    Redis and a live worker, and the language model. 503 with per-check detail if a required check fails;
    200 with status "degraded" if only the language model is unavailable (answers are then extractive)."""
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
    settings = get_settings()
    upload_path = settings.upload_path
    writable = upload_path.is_dir() and os.access(upload_path, os.W_OK)
    checks["uploads"] = HealthCheck(status="ok" if writable else "error",
                                    detail=None if writable else f"{upload_path} is not writable")
    models_ok, models_problem = await to_thread.run_sync(models_ready)
    checks["models"] = HealthCheck(status="ok" if models_ok else "error", detail=models_problem)
    checks.update(await to_thread.run_sync(_queue_checks, settings))
    llm = await get_llm().status()
    checks["llm"] = HealthCheck(status="ok" if llm["state"] in ("ok", "disabled") else "error", detail=llm["detail"])
    required_ok = all(c.status == "ok" for name, c in checks.items() if name not in OPTIONAL_CHECKS)
    body = HealthReady(status="ok" if all(c.status == "ok" for c in checks.values()) else "degraded", checks=checks)
    return JSONResponse(body.model_dump(), status_code=200 if required_ok else 503)


def _queue_checks(settings) -> dict[str, HealthCheck]:
    if settings.jobs_eager:
        inline = HealthCheck(status="ok", detail="inline mode: documents are processed in the API process")
        if not settings.redis_url:
            return {"redis": inline, "worker": inline}
        return {**_redis_check(settings), "worker": inline}
    import redis

    try:
        client = redis.Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1)
        client.ping()
        beat = client.get(HEARTBEAT_KEY)
    except redis.RedisError as exc:
        return {"redis": HealthCheck(status="error", detail=type(exc).__name__),
                "worker": HealthCheck(status="error", detail="unknown (Redis unreachable)")}
    if beat is None:
        worker = HealthCheck(status="error", detail="no heartbeat in the last 30 s; start the worker")
    else:
        worker = HealthCheck(status="ok", detail=f"last heartbeat {time.time() - float(beat):.0f} s ago")
    return {"redis": HealthCheck(status="ok"), "worker": worker}


def _redis_check(settings) -> dict[str, HealthCheck]:
    import redis

    try:
        redis.Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1).ping()
        return {"redis": HealthCheck(status="ok")}
    except redis.RedisError as exc:
        return {"redis": HealthCheck(status="error", detail=type(exc).__name__)}
