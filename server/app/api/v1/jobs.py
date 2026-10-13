"""Background job status."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ...db.models import Document, Job
from ...schemas.common import ERROR_RESPONSES, Problem
from ...schemas.documents import JobOut
from ..deps import CurrentUser, SessionDep

router = APIRouter(prefix="/jobs", tags=["jobs"], responses={401: ERROR_RESPONSES[401]})


@router.get("/{job_id}", response_model=JobOut, responses={404: {"model": Problem}})
async def get_job(job_id: int, session: SessionDep, _: CurrentUser) -> JobOut:
    row = (await session.execute(
        select(Job, Document.id).outerjoin(Document, Job.document_id == Document.id).where(Job.id == job_id)
    )).first()
    if row is None:
        raise HTTPException(404, "Job not found")
    job, document_id = row
    return JobOut(id=job.id, kind=job.kind, status=job.status, progress=job.progress,
                  documentId=str(document_id) if document_id else None, error=job.error,
                  createdAt=job.created_at, startedAt=job.started_at, finishedAt=job.finished_at)
