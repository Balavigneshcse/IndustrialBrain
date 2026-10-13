from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DocumentStatus = Literal["queued", "processing", "ready", "failed"]


class DocumentOut(BaseModel):
    id: str
    documentId: str
    originalName: str
    filename: str
    contentType: str
    sizeBytes: int
    size: int
    status: DocumentStatus
    documentType: str
    assetTags: str  # comma-separated, kept for the current UI
    summary: str
    errorMessage: str | None
    uploadedBy: str
    uploadedAt: datetime
    uploadDate: datetime
    chunkCount: int
    jobId: int | None = None


class JobOut(BaseModel):
    id: int
    kind: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int
    documentId: str | None
    error: str | None
    createdAt: datetime
    startedAt: datetime | None
    finishedAt: datetime | None
