from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    documentId: str
    originalName: str
    filename: str
    contentType: str
    sizeBytes: int
    size: int
    status: Literal["processing", "ready", "failed"]
    documentType: str
    assetTags: str  # comma-separated, kept for the current UI
    summary: str
    errorMessage: str | None
    uploadedBy: str
    uploadedAt: datetime
    uploadDate: datetime
