"""Question answering over the indexed evidence, and answer feedback."""
import time

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from ...core.config import get_settings
from ...core.ratelimit import limiter
from ...db.models import QueryLog
from ...schemas.chat import ChatAnswer, ChatQueryRequest, Citation, FeedbackRequest
from ...schemas.common import ERROR_RESPONSES, Ok, Problem
from ...services import store
from ...services.answers import ANSWER_MODE, INSUFFICIENT_EVIDENCE, classify_query, generate_answer
from ...services.entities import extract_entities
from ..deps import CurrentUser, SessionDep

router = APIRouter(prefix="/chat", tags=["chat"], responses={401: ERROR_RESPONSES[401]})


@router.post("/query", response_model=ChatAnswer, responses={429: ERROR_RESPONSES[429]})
async def chat_query(body: ChatQueryRequest, session: SessionDep, user: CurrentUser) -> ChatAnswer:
    settings = get_settings()
    limiter.check(f"chat:{user.id}", settings.chat_rate_per_minute)
    started = time.perf_counter()
    question = body.question.strip()
    asset_tag = (body.assetTag or "").strip()
    desired_format = body.desiredFormat or "quick_answer"

    # Asset tags named in the question (or the tag filter) that no indexed document mentions get an
    # explicit "no evidence" reply instead of an answer built from another asset's records.
    requested = set(extract_entities(question)["asset_tags"])
    if asset_tag:
        requested.add(asset_tag.upper())
    unknown = sorted(requested - await store.known_asset_tags(session)) if requested else []

    if unknown and len(unknown) == len(requested):
        evidence: list[dict] = []
        answer_text, mode, confidence = (
            f"No indexed documents mention {', '.join(unknown)}, so I can't answer about "
            f"{'it' if len(unknown) == 1 else 'them'}. Upload records for that equipment first.",
            ANSWER_MODE, 0.0,
        )
    else:
        evidence = await store.search(session, question, asset_tag, limit=5)
        weak = not evidence or evidence[0]["score"] < settings.min_evidence_score
        if weak and classify_query(question) != "greeting":
            # The reranker found nothing relevant enough: say so instead of answering from weak matches.
            evidence, answer_text, mode, confidence = [], INSUFFICIENT_EVIDENCE, ANSWER_MODE, 0.0
        else:
            answer_text, mode, confidence = await run_in_threadpool(generate_answer, question, evidence, desired_format)

    citations = [
        Citation(
            docId=str(item["metadata"]["document_id"]), filename=item["metadata"]["source"],
            source=item["metadata"]["source"], page=item["metadata"]["page"],
            documentType=item["metadata"]["document_type"], excerpt=item["text"][:360],
            textSnippet=item["text"][:360], relevance=round(item["score"], 2),
        )
        for item in evidence
    ]
    log = QueryLog(
        user_id=user.id, question=question, answer=answer_text, mode=mode, asset_tag=asset_tag,
        confidence=round(confidence, 2), latency_ms=round((time.perf_counter() - started) * 1000),
        retrieved_chunk_ids=[item["chunk_id"] for item in evidence],
    )
    session.add(log)
    await session.commit()
    return ChatAnswer(answer=answer_text, mode=mode, format=desired_format, confidence=round(confidence, 2),
                      citations=citations, assetTag=asset_tag.upper(), queryId=log.id)


@router.patch("/{query_id}/feedback", response_model=Ok, responses={403: ERROR_RESPONSES[403], 404: {"model": Problem}})
async def submit_feedback(query_id: int, body: FeedbackRequest, session: SessionDep, user: CurrentUser) -> Ok:
    log = await session.get(QueryLog, query_id)
    if log is None:
        raise HTTPException(404, "Query not found")
    if log.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "You can only rate your own answers")
    log.feedback = body.feedback
    await session.commit()
    return Ok()
