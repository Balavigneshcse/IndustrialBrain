"""Celery tasks. The work itself lives in services/jobs.py so the CLI can run it inline too."""
import asyncio

import structlog

from ..services.jobs import fail_job, run_job
from .celery_app import celery_app

log = structlog.get_logger("worker")


@celery_app.task(name="indusmind.process_document", bind=True, max_retries=3, default_retry_delay=15)
def process_document(self, job_id: int) -> None:
    """Extract, chunk, tag, embed and index one document. Extraction problems mark the document
    failed without raising; anything raised here is infrastructure (database, models) and is retried."""
    try:
        asyncio.run(run_job(job_id))
    except Exception as exc:
        if self.request.is_eager or self.request.retries >= self.max_retries:
            log.exception("job_failed", job_id=job_id)
            asyncio.run(fail_job(job_id, f"Processing failed: {exc}"))
            return
        raise self.retry(exc=exc)
