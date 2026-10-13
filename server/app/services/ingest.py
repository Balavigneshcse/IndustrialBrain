"""Turn a stored file into indexed evidence. Shared by the upload endpoint and the CLI importer."""
from pathlib import Path

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..db.models import Document
from . import store
from .extraction import classify_document, extract_entities, extract_text
from .indexing import chunk_pages


def stored_path(doc: Document) -> Path:
    """Uploads are stored as <public_id><lower-case suffix> in UPLOAD_DIR."""
    return get_settings().upload_path / f"{doc.public_id}{Path(doc.original_name).suffix.lower()[:16]}"


def _analyse(path: Path, name: str) -> tuple[dict, str, list[dict]]:
    """CPU-bound part of ingestion; runs in a worker thread (a background queue in Phase 2)."""
    full_text, pages = extract_text(path)
    return extract_entities(full_text), classify_document(name, full_text), chunk_pages(pages)


async def ingest(session: AsyncSession, doc: Document) -> None:
    """Extract, chunk and index `doc` (already flushed, file already at stored_path).

    Unreadable or unsupported content marks the document "failed" with a reason and indexes nothing.
    """
    try:
        entities, doc_type, chunks = await to_thread.run_sync(_analyse, stored_path(doc), doc.original_name)
    except Exception as exc:
        doc.status, doc.error_message = "failed", str(exc)[:2000]
        return
    count = await store.index_document(session, doc, chunks, entities)
    doc.status, doc.document_type, doc.asset_tags, doc.chunk_count = "ready", doc_type, entities["asset_tags"], count
    doc.error_message = None
    doc.summary = f"Indexed {count} evidence chunks and found {len(entities['asset_tags'])} asset tags."
