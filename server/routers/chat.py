"""Chat router — RAG query endpoint + feedback."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from ..database import get_db
from ..models import QueryLog
from ..security.jwt import get_current_user
from ..services.extraction import extract_entities
from ..services.rag_service import rag, ANSWER_MODE

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ConversationTurn(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None


class ChatQueryRequest(BaseModel):
    question: str
    assetTag: Optional[str] = ""
    desiredFormat: Optional[str] = "quick_answer"
    history: Optional[List[ConversationTurn]] = []


class FeedbackRequest(BaseModel):
    feedback: Optional[int] = None


@router.post("/query")
def chat_query(body: ChatQueryRequest, db: Session = Depends(get_db),
               user: dict = Depends(get_current_user)):
    question = body.question.strip()
    asset_tag = (body.assetTag or "").strip()

    # Asset tags named in the question (or the tag filter) that no indexed document mentions
    # get an explicit "no evidence" reply instead of an answer built from another asset's records.
    requested_tags = set(extract_entities(question)["asset_tags"])
    if asset_tag:
        requested_tags.add(asset_tag.upper())
    unknown_tags = sorted(requested_tags - rag.known_asset_tags()) if requested_tags else []

    if unknown_tags and len(unknown_tags) == len(requested_tags):
        evidence = []
        answer_text, mode, confidence = (
            f"No indexed documents mention {', '.join(unknown_tags)}, so I can't answer about "
            f"{'it' if len(unknown_tags) == 1 else 'them'}. Upload records for that equipment first.",
            ANSWER_MODE, 0.0,
        )
    else:
        evidence = rag.search(question, asset_tag, limit=5)
        # Generate answer (handles greeting/document/industrial routing internally)
        answer_text, mode, confidence = rag.generate_answer(
            question, evidence, body.desiredFormat or "quick_answer",
        )

    # Build citations
    citations = [
        {
            "docId": str(item["metadata"].get("document_id", "")),
            "filename": item["metadata"].get("source", "Uploaded Document"),
            "source": item["metadata"].get("source", "Uploaded Document"),
            "page": item["metadata"].get("page", 1),
            "documentType": item["metadata"].get("document_type", ""),
            "excerpt": item["text"][:360],
            "textSnippet": item["text"][:360],
            "relevance": round(min(0.97, 0.5 + item["score"] * 0.45), 2),
        }
        for item in evidence
    ]

    # Save to query log
    log = QueryLog(
        question=question,
        answer=answer_text,
        mode=mode,
        asset_tag=asset_tag,
        confidence=round(confidence, 2),
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return {
        "answer": answer_text,
        "mode": mode,
        "format": body.desiredFormat or "quick_answer",
        "confidence": round(confidence, 2),
        "citations": citations,
        "assetTag": asset_tag.upper() if asset_tag else "",
        "queryId": log.id,
    }


@router.patch("/{query_id}/feedback")
def submit_feedback(query_id: int, body: FeedbackRequest,
                    db: Session = Depends(get_db),
                    user: dict = Depends(get_current_user)):
    log = db.query(QueryLog).filter(QueryLog.id == query_id).first()
    if log:
        log.feedback = body.feedback
        db.commit()
    return {"ok": True}
