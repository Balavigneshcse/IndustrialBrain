"""Document upload, listing and deletion."""
import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import select

from ...core.config import get_settings
from ...core.ratelimit import limiter
from ...db.models import Document, User
from ...schemas.common import ERROR_RESPONSES, Ok, Problem
from ...schemas.documents import DocumentOut
from ...services import audit
from ...services.ingest import ingest, stored_path
from ..deps import CurrentUser, EngineerUser, SessionDep

router = APIRouter(prefix="/documents", tags=["documents"], responses={401: ERROR_RESPONSES[401]})


def document_out(doc: Document, uploader: str | None) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id), documentId=doc.public_id, originalName=doc.original_name, filename=doc.original_name,
        contentType=doc.content_type, sizeBytes=doc.size_bytes, size=doc.size_bytes, status=doc.status,
        documentType=doc.document_type, assetTags=",".join(doc.asset_tags or []), summary=doc.summary,
        errorMessage=doc.error_message, uploadedBy=uploader or "", uploadedAt=doc.uploaded_at,
        uploadDate=doc.uploaded_at,
    )


@router.post("/upload", response_model=DocumentOut, responses={
    403: ERROR_RESPONSES[403], 413: {"model": Problem, "description": "File larger than MAX_UPLOAD_MB"},
    429: ERROR_RESPONSES[429]})
async def upload_document(request: Request, session: SessionDep, user: EngineerUser,
                          file: UploadFile = File(...)) -> DocumentOut:
    """Store and index a document. Extraction problems return status "failed" with an errorMessage."""
    settings = get_settings()
    limiter.check(f"upload:{user.id}", settings.upload_rate_per_minute)
    name = Path(file.filename or "untitled.txt").name[:512] or "untitled.txt"
    doc = Document(public_id=str(uuid.uuid4()), original_name=name, content_type=(file.content_type or "")[:128],
                   size_bytes=0, sha256="", status="processing", uploaded_by_id=user.id)
    path = stored_path(doc)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Stream to disk with a size cap instead of reading the whole upload into memory.
    limit = settings.max_upload_mb * 1024 * 1024
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("wb") as out:
            while block := await file.read(1024 * 1024):
                size += len(block)
                if size > limit:
                    raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB upload limit")
                digest.update(block)
                out.write(block)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    doc.size_bytes, doc.sha256 = size, digest.hexdigest()
    session.add(doc)
    await session.flush()

    await ingest(session, doc)

    audit.record(session, "document_uploaded", user=user, request=request, target_type="document",
                 target_id=doc.id, detail={"name": name, "status": doc.status, "sizeBytes": size})
    await session.commit()
    await session.refresh(doc)
    return document_out(doc, user.username)


@router.get("", response_model=list[DocumentOut])
async def list_documents(session: SessionDep, _: CurrentUser,
                         limit: int = Query(500, ge=1, le=1000), offset: int = Query(0, ge=0)) -> list[DocumentOut]:
    rows = await session.execute(
        select(Document, User.username).outerjoin(User, Document.uploaded_by_id == User.id)
        .order_by(Document.id.desc()).limit(limit).offset(offset)
    )
    return [document_out(doc, uploader) for doc, uploader in rows.all()]


@router.delete("/{doc_id}", response_model=Ok, responses={403: ERROR_RESPONSES[403], 404: {"model": Problem}})
async def delete_document(doc_id: int, request: Request, session: SessionDep, user: CurrentUser) -> Ok:
    """Engineers can delete their own uploads; admins can delete any document."""
    doc = await session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    if user.role == "viewer" or (user.role == "engineer" and doc.uploaded_by_id != user.id):
        raise HTTPException(403, "You can only delete documents you uploaded")
    stored_path(doc).unlink(missing_ok=True)
    audit.record(session, "document_deleted", user=user, request=request, target_type="document",
                 target_id=doc.id, detail={"name": doc.original_name})
    await session.delete(doc)  # chunks are removed by ON DELETE CASCADE
    await session.commit()
    return Ok()
