"""Question answering over the indexed evidence (JSON or streamed), and answer feedback."""
import json

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ...core.config import get_settings
from ...core.ratelimit import limiter
from ...db.models import QueryLog
from ...db.session import get_sessionmaker
from ...schemas.chat import ChatAnswer, ChatQueryRequest, FeedbackRequest
from ...schemas.common import ERROR_RESPONSES, Ok, Problem
from ...services.qa import answer_events
from ..deps import CurrentUser, SessionDep

router = APIRouter(prefix="/chat", tags=["chat"], responses={401: ERROR_RESPONSES[401]})
log = structlog.get_logger("chat")


@router.post("/query", response_model=ChatAnswer, responses={429: ERROR_RESPONSES[429]})
async def chat_query(body: ChatQueryRequest, session: SessionDep, user: CurrentUser) -> ChatAnswer:
    """Answer a question from the indexed documents. Waits for the complete answer; use /chat/stream to
    show it while it is generated."""
    limiter.check(f"chat:{user.id}", get_settings().chat_rate_per_minute)
    final = None
    async for event in answer_events(session, user.id, body):
        if event["event"] == "done":
            final = event["data"]
    return ChatAnswer(**final)


@router.post("/stream", response_class=StreamingResponse, responses={
    200: {"content": {"text/event-stream": {}}, "description": (
        "Server-Sent Events: `status` {stage, position?}, `sources` {question, citations}, `token` {text} "
        "(repeated), then `done` with the ChatAnswer, or `error` with a problem body. Close the connection "
        "to stop generation.")},
    429: ERROR_RESPONSES[429]})
async def chat_stream(body: ChatQueryRequest, user: CurrentUser) -> StreamingResponse:
    limiter.check(f"chat:{user.id}", get_settings().chat_rate_per_minute)
    user_id = user.id

    async def stream():
        async with get_sessionmaker()() as session:
            try:
                async for event in answer_events(session, user_id, body):
                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            except HTTPException as exc:
                problem = {"title": "Too Many Requests" if exc.status_code == 429 else "Error",
                           "status": exc.status_code, "detail": exc.detail}
                yield f"event: error\ndata: {json.dumps(problem)}\n\n"
            except Exception:
                log.exception("chat_stream_failed")
                yield ('event: error\ndata: {"title": "Internal Server Error", "status": 500, '
                       '"detail": "The answer could not be completed."}\n\n')

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.patch("/{query_id}/feedback", response_model=Ok, responses={403: ERROR_RESPONSES[403], 404: {"model": Problem}})
async def submit_feedback(query_id: int, body: FeedbackRequest, session: SessionDep, user: CurrentUser) -> Ok:
    log_row = await session.get(QueryLog, query_id)
    if log_row is None:
        raise HTTPException(404, "Query not found")
    if log_row.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "You can only rate your own answers")
    log_row.feedback = body.feedback
    await session.commit()
    return Ok()
