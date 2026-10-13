"""Background jobs: queue document processing and run it (in the Celery worker, or inline when no
Redis is configured)."""
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ..core.config import get_settings
from ..db.models import Document, Job, User
from .ingest import ingest

log = structlog.get_logger("jobs")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def enqueue_processing(session: AsyncSession, doc: Document, user: User | None, kind: str = "ingest") -> Job:
    """Create a job for `doc` and hand it to the worker. Inline mode processes it before returning."""
    from ..workers.tasks import process_document

    job = Job(kind=kind, document_id=doc.id, created_by_id=user.id if user else None)
    doc.status, doc.error_message = "queued", None
    session.add(job)
    await session.commit()
    try:
        await run_in_threadpool(process_document.delay, job.id)
    except Exception as exc:  # broker unreachable
        log.error("enqueue_failed", job_id=job.id, error=str(exc))
        job.status, job.error, job.finished_at = "failed", "Background queue unavailable", _now()
        doc.status, doc.error_message = "failed", "Background queue unavailable; try again shortly"
        await session.commit()
        raise HTTPException(503, "Background processing is unavailable; try again shortly") from exc
    await session.refresh(job)
    await session.refresh(doc)
    return job


def _job_session():
    # Each task runs its own event loop, so it gets its own engine without a shared pool.
    engine = create_async_engine(get_settings().sqlalchemy_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def run_job(job_id: int) -> None:
    engine, sessions = _job_session()
    try:
        async with sessions() as session:
            job = await session.get(Job, job_id)
            if job is None or job.status == "succeeded":
                return
            doc = await session.get(Document, job.document_id) if job.document_id else None
            if doc is None:
                job.status, job.error, job.finished_at = "failed", "Document no longer exists", _now()
                await session.commit()
                return
            job.status, job.started_at, job.progress = "running", _now(), 5
            doc.status = "processing"
            await session.commit()

            async def progress(percent: int) -> None:
                job.progress = percent
                await session.commit()

            await ingest(session, doc, progress)
            job.status = "succeeded" if doc.status == "ready" else "failed"
            job.error, job.progress, job.finished_at = doc.error_message, 100, _now()
            await session.commit()
            log.info("job_finished", job_id=job.id, status=job.status, document=doc.original_name)
    finally:
        await engine.dispose()


async def fail_job(job_id: int, reason: str) -> None:
    engine, sessions = _job_session()
    try:
        async with sessions() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.status, job.error, job.finished_at = "failed", reason[:2000], _now()
            doc = await session.get(Document, job.document_id) if job.document_id else None
            if doc is not None and doc.status in ("queued", "processing"):
                doc.status, doc.error_message = "failed", reason[:2000]
            await session.commit()
    finally:
        await engine.dispose()
