"""Evidence store on PostgreSQL + pgvector (replaces the embedded ChromaDB collection)."""
from sqlalchemy import Text, cast, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Chunk, Document
from .answers import FILE_PATTERN
from .indexing import embedding

ENTITY_KEYS = ("failures", "actions", "dates", "measurements")


def _evidence(chunk: Chunk, document: Document, score: float) -> dict:
    """Shape a chunk like the evidence items the answer templates expect."""
    meta = {
        "source": document.original_name,
        "page": chunk.page,
        "document_id": document.public_id,
        "document_type": document.document_type,
        "asset_tags": ",".join(chunk.asset_tags or []),
        **{key: ",".join((chunk.entities or {}).get(key, [])) for key in ENTITY_KEYS},
    }
    return {"text": chunk.text, "metadata": meta, "score": round(score, 4), "chunk_id": chunk.id}


async def index_document(session: AsyncSession, document: Document, chunks: list[dict], entities: dict) -> int:
    await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    session.add_all(
        Chunk(
            document_id=document.id, ordinal=i, page=int(c["page"]), text=c["text"],
            embedding=embedding(c["text"]), asset_tags=list(entities.get("asset_tags", [])),
            entities={key: list(entities.get(key, [])) for key in ENTITY_KEYS},
        )
        for i, c in enumerate(chunks)
    )
    return len(chunks)


async def search(session: AsyncSession, question: str, asset_tag: str = "", limit: int = 5) -> list[dict]:
    # A question naming an exact uploaded filename is scoped to that file. Partial name matches are
    # deliberately not used (a file called "pump.txt" used to capture every "pump" question).
    file_match = FILE_PATTERN.search(question)
    if file_match:
        items = await search_by_source(session, file_match.group(0), limit, exact=True)
        if items:
            return items

    tag = asset_tag.strip().upper()
    distance = Chunk.embedding.cosine_distance(embedding(f"{question} {tag}")).label("distance")
    stmt = (select(Chunk, Document, distance).join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "ready").order_by(distance, Chunk.id).limit(limit))
    if tag:
        stmt = stmt.where(Chunk.asset_tags.contains([tag]))  # exact tag, uses the GIN index
        # Let the HNSW scan continue past filtered-out rows instead of returning too few results.
        await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    rows = (await session.execute(stmt)).all()
    return [_evidence(chunk, doc, max(0.0, 1.0 - dist)) for chunk, doc, dist in rows]


async def search_by_source(session: AsyncSession, name: str, limit: int = 5, exact: bool = False) -> list[dict]:
    name = name.strip().lower()
    if not name:
        return []
    source = func.lower(Document.original_name)
    condition = source == name if exact else source.contains(name, autoescape=True)
    stmt = (select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "ready", condition).order_by(Document.id, Chunk.ordinal).limit(limit))
    return [_evidence(chunk, doc, 0.85) for chunk, doc in (await session.execute(stmt)).all()]


async def asset_evidence(session: AsyncSession, tag: str) -> list[dict]:
    stmt = (select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "ready", Chunk.asset_tags.contains([tag.strip().upper()]))
            .order_by(Document.id, Chunk.ordinal))
    return [_evidence(chunk, doc, 1.0) for chunk, doc in (await session.execute(stmt)).all()]


async def known_asset_tags(session: AsyncSession) -> set[str]:
    stmt = (select(func.unnest(Chunk.asset_tags)).join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "ready").distinct())
    return set((await session.execute(stmt)).scalars())


async def chunk_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count(Chunk.id)))).scalar_one()


async def chunk_entities(session: AsyncSession) -> list[tuple[list[str], dict, str]]:
    """(asset_tags, entities, document public id) for every indexed chunk, for analytics."""
    stmt = (select(Chunk.asset_tags, Chunk.entities, cast(Document.public_id, Text))
            .join(Document, Chunk.document_id == Document.id).where(Document.status == "ready"))
    return [tuple(row) for row in (await session.execute(stmt)).all()]
