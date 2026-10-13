"""Turn a stored file into indexed evidence: extract, classify, chunk by structure, tag each chunk,
derive asset events, embed, and store. Shared by the background worker, inline processing and the CLI."""
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..db.models import Asset, Document
from . import store
from .chunking import chunk_pages
from .entities import asset_mentions, classify_document, extract_entities
from .events import chunk_events
from .extraction import extract_text
from .models import embed_passages

TABULAR_SUFFIXES = {".csv", ".xlsx", ".xls"}
ENTITY_KEYS = ("failures", "actions", "dates", "measurements")
Progress = Callable[[int], Awaitable[None]]


def stored_path(doc: Document) -> Path:
    """Uploads are stored as <public_id><lower-case suffix> in UPLOAD_DIR."""
    return get_settings().upload_path / f"{doc.public_id}{Path(doc.original_name).suffix.lower()[:16]}"


def _title(name: str) -> str:
    return re.sub(r"[_\-.]+", " ", Path(name).stem).strip()


def analyse(path: Path, name: str, registry: set[str] | None) -> dict:
    """CPU-bound part of ingestion (extraction, entities, embeddings); runs in a worker thread."""
    full_text, pages = extract_text(path)
    document_type = classify_document(name, full_text)
    document = extract_entities(full_text, registry)
    title_tags, _ = asset_mentions(full_text[:400], registry)
    subject = title_tags or document["asset_tags"]
    # A document with exactly one date (e.g. an inspection report) dates every finding in it.
    fallback_date = document["dates"][0] if len(document["dates"]) == 1 else None

    chunks = chunk_pages(pages, tabular=path.suffix.lower() in TABULAR_SUFFIXES)
    for chunk in chunks:
        entities = extract_entities(chunk["text"], registry)
        chunk["asset_tags"] = entities["asset_tags"] or subject
        chunk["entities"] = {key: entities[key] for key in ENTITY_KEYS}
        chunk["events"] = chunk_events(chunk["text"], chunk["asset_tags"], document_type, fallback_date, registry)
    # Prefix the title and section so a chunk like "Findings: ..." still knows which document it is in.
    embeddings = embed_passages([f"{_title(name)}. {c['section']}. {c['text']}" for c in chunks]) if chunks else []
    for chunk, vector in zip(chunks, embeddings):
        chunk["embedding"] = vector
    tags = sorted(set(subject) | {tag for c in chunks for tag in c["asset_tags"]})
    return {"document_type": document_type, "asset_tags": tags, "chunks": chunks}


async def registry_tags(session: AsyncSession) -> set[str]:
    return set((await session.execute(select(Asset.tag))).scalars())


async def ingest(session: AsyncSession, doc: Document, progress: Progress | None = None) -> None:
    """Index `doc` (already flushed, file at stored_path). Unreadable or unsupported content marks the
    document "failed" with a reason and indexes nothing."""
    registry = await registry_tags(session)
    if progress:
        await progress(10)
    try:
        result = await to_thread.run_sync(analyse, stored_path(doc), doc.original_name, registry or None)
    except Exception as exc:
        doc.status, doc.error_message = "failed", str(exc)[:2000]
        return
    if progress:
        await progress(80)
    chunk_count, event_count = await store.index_document(session, doc, result["chunks"])
    doc.status, doc.error_message = "ready", None
    doc.document_type, doc.asset_tags, doc.chunk_count = result["document_type"], result["asset_tags"], chunk_count
    doc.summary = (f"Indexed {chunk_count} evidence chunks with {event_count} asset events "
                   f"for {', '.join(result['asset_tags']) or 'no identified equipment'}.")
