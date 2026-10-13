"""Evidence store on PostgreSQL + pgvector: chunk/event indexing and hybrid retrieval.

Retrieval = vector search (bge-small, HNSW cosine) + keyword search (Postgres full text), merged
with reciprocal-rank fusion, then reranked by a cross-encoder. Evidence scores are the reranker's
relevance probability (0..1).
"""
import re

from anyio import to_thread
from sqlalchemy import Text, cast, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..db.models import AssetEvent, Chunk, Document
from .answers import FILE_PATTERN
from .models import embed_query, rerank

ENTITY_KEYS = ("failures", "actions", "dates", "measurements")
RRF_K = 60
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")


def _evidence(chunk: Chunk, document: Document, score: float) -> dict:
    """Shape a chunk like the evidence items the answer templates expect."""
    meta = {
        "source": document.original_name,
        "page": chunk.page,
        "section": chunk.section,
        "document_id": document.public_id,
        "document_type": document.document_type,
        "asset_tags": ",".join(chunk.asset_tags or []),
        **{key: ",".join((chunk.entities or {}).get(key, [])) for key in ENTITY_KEYS},
    }
    return {"text": chunk.text, "metadata": meta, "score": round(score, 4), "chunk_id": chunk.id}


async def index_document(session: AsyncSession, document: Document, chunks: list[dict]) -> tuple[int, int]:
    """Replace the document's chunks and events. Returns (chunks, events) stored."""
    await session.execute(delete(AssetEvent).where(AssetEvent.document_id == document.id))
    await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    rows = [
        Chunk(document_id=document.id, ordinal=i, page=int(c["page"]), section=c["section"][:200],
              word_count=c["words"], text=c["text"], embedding=c["embedding"],
              asset_tags=c["asset_tags"], entities=c["entities"])
        for i, c in enumerate(chunks)
    ]
    session.add_all(rows)
    await session.flush()
    seen: set[tuple] = set()
    events = []
    for row, chunk in zip(rows, chunks):
        for event in chunk["events"]:
            key = (event["asset_tag"], event["event_date"], event["kind"], event["label"])
            if key not in seen:
                seen.add(key)
                events.append(AssetEvent(document_id=document.id, chunk_id=row.id, **event))
    session.add_all(events)
    return len(rows), len(events)


async def search(session: AsyncSession, question: str, asset_tag: str = "", limit: int = 5) -> list[dict]:
    settings = get_settings()
    # A question naming an exact uploaded filename is scoped to that file (partial names are not used:
    # a file called "pump.txt" used to capture every "pump" question).
    file_match = FILE_PATTERN.search(question)
    if file_match:
        items = await search_by_source(session, file_match.group(0), limit, exact=True)
        if items:
            return items

    tag = asset_tag.strip().upper()
    ready = Document.status == "ready"
    k = settings.retrieval_candidates

    query_vector = await to_thread.run_sync(embed_query, question)
    distance = Chunk.embedding.cosine_distance(query_vector)
    vector_stmt = select(Chunk.id).join(Document, Chunk.document_id == Document.id).where(ready)
    keyword_ids: list[int] = []
    words = WORD.findall(question)
    if tag:
        vector_stmt = vector_stmt.where(Chunk.asset_tags.contains([tag]))
        # Let the HNSW scan continue past filtered-out rows instead of returning too few results.
        await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    vector_ids = list((await session.execute(vector_stmt.order_by(distance, Chunk.id).limit(k))).scalars())

    if words:
        tsquery = func.websearch_to_tsquery("english", " OR ".join(f'"{w}"' for w in words))
        keyword_stmt = (select(Chunk.id).join(Document, Chunk.document_id == Document.id)
                        .where(ready, Chunk.tsv.op("@@")(tsquery)))
        if tag:
            keyword_stmt = keyword_stmt.where(Chunk.asset_tags.contains([tag]))
        keyword_stmt = keyword_stmt.order_by(func.ts_rank_cd(Chunk.tsv, tsquery).desc(), Chunk.id).limit(k)
        keyword_ids = list((await session.execute(keyword_stmt)).scalars())

    fused: dict[int, float] = {}
    for ranked in (vector_ids, keyword_ids):
        for rank, chunk_id in enumerate(ranked):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    candidate_ids = sorted(fused, key=lambda cid: (-fused[cid], cid))[:settings.rerank_candidates]
    if not candidate_ids:
        return []

    rows = (await session.execute(
        select(Chunk, Document).join(Document, Chunk.document_id == Document.id).where(Chunk.id.in_(candidate_ids))
    )).all()
    by_id = {chunk.id: (chunk, doc) for chunk, doc in rows}
    candidates = [by_id[cid] for cid in candidate_ids if cid in by_id]
    passages = [f"{c.section}: {c.text}" if c.section and not c.text.startswith(c.section) else c.text
                for c, _ in candidates]
    scores = await to_thread.run_sync(rerank, question, passages)
    ranked = sorted(zip(candidates, scores), key=lambda item: -item[1])
    return [_evidence(chunk, doc, score) for (chunk, doc), score in ranked[:limit]]


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
    """Chunks whose subject equipment includes `tag` (exact match)."""
    stmt = (select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "ready", Chunk.asset_tags.contains([tag.strip().upper()]))
            .order_by(Document.id, Chunk.ordinal))
    return [_evidence(chunk, doc, 1.0) for chunk, doc in (await session.execute(stmt)).all()]


async def asset_events(session: AsyncSession, tag: str) -> list[tuple[AssetEvent, str]]:
    """(event, source document name), chronological; undated events last."""
    stmt = (select(AssetEvent, Document.original_name).join(Document, AssetEvent.document_id == Document.id)
            .where(Document.status == "ready", AssetEvent.asset_tag == tag.strip().upper())
            .order_by(AssetEvent.event_date.asc().nulls_last(), AssetEvent.kind, AssetEvent.label))
    return [tuple(row) for row in (await session.execute(stmt)).all()]


async def all_events(session: AsyncSession) -> list[tuple[str, str, str, object, int]]:
    """(asset_tag, kind, label, event_date, document_id) for every event of a ready document."""
    stmt = (select(AssetEvent.asset_tag, AssetEvent.kind, AssetEvent.label, AssetEvent.event_date,
                   AssetEvent.document_id)
            .join(Document, AssetEvent.document_id == Document.id).where(Document.status == "ready"))
    return [tuple(row) for row in (await session.execute(stmt)).all()]


async def known_asset_tags(session: AsyncSession) -> set[str]:
    stmt = (select(func.unnest(Chunk.asset_tags)).join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "ready").distinct())
    return set((await session.execute(stmt)).scalars())


async def chunk_count(session: AsyncSession) -> int:
    stmt = select(func.count(Chunk.id)).join(Document, Chunk.document_id == Document.id).where(Document.status == "ready")
    return (await session.execute(stmt)).scalar_one()


async def chunk_entities(session: AsyncSession) -> list[tuple[list[str], dict, str]]:
    """(asset_tags, entities, document public id) for every indexed chunk."""
    stmt = (select(Chunk.asset_tags, Chunk.entities, cast(Document.public_id, Text))
            .join(Document, Chunk.document_id == Document.id).where(Document.status == "ready"))
    return [tuple(row) for row in (await session.execute(stmt)).all()]
