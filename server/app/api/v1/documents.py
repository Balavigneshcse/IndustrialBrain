"""Documents: upload (processed in the background), listing, status, live progress, re-index, delete."""
import asyncio
import hashlib
import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from ...core.config import get_settings
from ...core.errors import problem
from ...core.ratelimit import limiter
from ...db.models import Document, Job, User
from ...db.session import get_sessionmaker
from ...schemas.common import ERROR_RESPONSES, Ok, Problem
from ...schemas.documents import DocumentOut
from ...services import audit
from ...services.ingest import stored_path
from ...services.jobs import enqueue_processing
from ...services.uploads import file_type_problem
from ..deps import CurrentUser, EngineerUser, SessionDep

router = APIRouter(prefix="/documents", tags=["documents"], responses={401: ERROR_RESPONSES[401]})
TERMINAL = {"ready", "failed"}


def document_out(doc: Document, uploader: str | None, job_id: int | None = None) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id), documentId=doc.public_id, originalName=doc.original_name, filename=doc.original_name,
        contentType=doc.content_type, sizeBytes=doc.size_bytes, size=doc.size_bytes, status=doc.status,
        documentType=doc.document_type, assetTags=",".join(doc.asset_tags or []), summary=doc.summary,
        errorMessage=doc.error_message, uploadedBy=uploader or "", uploadedAt=doc.uploaded_at,
        uploadDate=doc.uploaded_at, chunkCount=doc.chunk_count, jobId=job_id,
    )


async def _get_document(session: SessionDep, doc_id: int) -> tuple[Document, str | None]:
    row = (await session.execute(
        select(Document, User.username).outerjoin(User, Document.uploaded_by_id == User.id).where(Document.id == doc_id)
    )).first()
    if row is None:
        raise HTTPException(404, "Document not found")
    return row[0], row[1]


def _can_modify(user: User, doc: Document) -> bool:
    return user.role == "admin" or (user.role == "engineer" and doc.uploaded_by_id == user.id)


@router.post("/upload", response_model=DocumentOut, status_code=202, responses={
    403: ERROR_RESPONSES[403],
    409: {"model": Problem, "description": "The same file was already uploaded (SHA-256 match)"},
    413: {"model": Problem, "description": "File larger than MAX_UPLOAD_MB"},
    415: {"model": Problem, "description": "File type not allowed, or content does not match the extension"},
    429: ERROR_RESPONSES[429], 503: {"model": Problem, "description": "Background processing unavailable"}})
async def upload_document(request: Request, session: SessionDep, user: EngineerUser,
                          file: UploadFile = File(...)):
    """Store the file and queue it for processing (status "queued"). Follow progress with
    GET /documents/{id}, GET /jobs/{jobId} or the /documents/{id}/events stream."""
    settings = get_settings()
    limiter.check(f"upload:{user.id}", settings.upload_rate_per_minute)
    name = Path(file.filename or "untitled.txt").name[:512] or "untitled.txt"
    first = await file.read(1024 * 1024)
    if type_problem := file_type_problem(name, first[:4096]):
        raise HTTPException(415, type_problem)

    doc = Document(public_id=str(uuid.uuid4()), original_name=name, content_type=(file.content_type or "")[:128],
                   size_bytes=0, sha256="", status="queued", uploaded_by_id=user.id)
    path = stored_path(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    limit = settings.max_upload_mb * 1024 * 1024
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("wb") as out:  # streamed with a size cap, never fully in memory
            block = first
            while block:
                size += len(block)
                if size > limit:
                    raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB upload limit")
                digest.update(block)
                out.write(block)
                block = await file.read(1024 * 1024)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise

    duplicate = (await session.execute(
        select(Document).where(Document.sha256 == digest.hexdigest(), Document.status != "failed")
    )).scalars().first()
    if duplicate is not None:
        path.unlink(missing_ok=True)
        return problem(request, 409, f"This file was already uploaded as '{duplicate.original_name}'",
                       documentId=str(duplicate.id))

    doc.size_bytes, doc.sha256 = size, digest.hexdigest()
    session.add(doc)
    await session.flush()
    audit.record(session, "document_uploaded", user=user, request=request, target_type="document",
                 target_id=doc.id, detail={"name": name, "sizeBytes": size})
    job = await enqueue_processing(session, doc, user)
    return JSONResponse(document_out(doc, user.username, job.id).model_dump(mode="json"), status_code=202)


@router.get("", response_model=list[DocumentOut])
async def list_documents(session: SessionDep, _: CurrentUser,
                         limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)) -> list[DocumentOut]:
    rows = await session.execute(
        select(Document, User.username).outerjoin(User, Document.uploaded_by_id == User.id)
        .order_by(Document.id.desc()).limit(limit).offset(offset)
    )
    return [document_out(doc, uploader) for doc, uploader in rows.all()]


@router.get("/{doc_id}", response_model=DocumentOut, responses={404: {"model": Problem}})
async def get_document(doc_id: int, session: SessionDep, _: CurrentUser) -> DocumentOut:
    doc, uploader = await _get_document(session, doc_id)
    job_id = (await session.execute(
        select(Job.id).where(Job.document_id == doc.id).order_by(Job.id.desc()).limit(1))).scalar()
    return document_out(doc, uploader, job_id)


@router.get("/{doc_id}/events", response_class=StreamingResponse, responses={
    200: {"content": {"text/event-stream": {}}, "description": "Server-Sent Events: one `status` event per change"},
    404: {"model": Problem}})
async def document_events(doc_id: int, session: SessionDep, _: CurrentUser) -> StreamingResponse:
    """Live processing status. Emits `status` events ({status, progress, errorMessage}) until the
    document is ready or failed (or 15 minutes pass)."""
    await _get_document(session, doc_id)

    async def stream():
        last, last_sent, deadline = None, time.monotonic(), time.monotonic() + 900
        while time.monotonic() < deadline:
            async with get_sessionmaker()() as poll:
                doc = await poll.get(Document, doc_id)
                job = (await poll.execute(select(Job).where(Job.document_id == doc_id)
                                          .order_by(Job.id.desc()).limit(1))).scalar()
            if doc is None:
                yield "event: status\ndata: {\"status\": \"deleted\"}\n\n"
                return
            state = {"status": doc.status, "progress": job.progress if job else 100, "errorMessage": doc.error_message}
            if state != last:
                yield f"event: status\ndata: {json.dumps(state)}\n\n"
                last, last_sent = state, time.monotonic()
            if doc.status in TERMINAL:
                return
            if time.monotonic() - last_sent > 15:
                yield ": keep-alive\n\n"
                last_sent = time.monotonic()
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/{doc_id}/reindex", response_model=DocumentOut, status_code=202,
             responses={403: ERROR_RESPONSES[403], 404: {"model": Problem}, 409: {"model": Problem}})
async def reindex_document(doc_id: int, request: Request, session: SessionDep, user: CurrentUser):
    """Re-run extraction and indexing (e.g. after importing the asset registry)."""
    doc, uploader = await _get_document(session, doc_id)
    if not _can_modify(user, doc):
        raise HTTPException(403, "You can only re-index documents you uploaded")
    if doc.status in ("queued", "processing"):
        raise HTTPException(409, "This document is already being processed")
    if not stored_path(doc).is_file():
        raise HTTPException(409, "The original file is no longer stored; upload it again")
    audit.record(session, "document_reindexed", user=user, request=request, target_type="document", target_id=doc.id)
    job = await enqueue_processing(session, doc, user, kind="reindex")
    return JSONResponse(document_out(doc, uploader, job.id).model_dump(mode="json"), status_code=202)


@router.delete("/{doc_id}", response_model=Ok, responses={403: ERROR_RESPONSES[403], 404: {"model": Problem}})
async def delete_document(doc_id: int, request: Request, session: SessionDep, user: CurrentUser) -> Ok:
    """Engineers can delete their own uploads; admins can delete any document."""
    doc, _ = await _get_document(session, doc_id)
    if not _can_modify(user, doc):
        raise HTTPException(403, "You can only delete documents you uploaded")
    stored_path(doc).unlink(missing_ok=True)
    audit.record(session, "document_deleted", user=user, request=request, target_type="document",
                 target_id=doc.id, detail={"name": doc.original_name})
    await session.delete(doc)  # chunks, events and jobs are removed by ON DELETE CASCADE
    await session.commit()
    return Ok()
