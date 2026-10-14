from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    role: str | None = None   # "user", or "assistant" / "ai" for earlier answers
    content: str | None = None


class ChatQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    assetTag: str | None = Field(default="", max_length=32)
    desiredFormat: str | None = Field(
        default="quick_answer", max_length=32,
        description="quick_answer | paragraph | bullet | table | report | work_order | checklist")
    history: list[ConversationTurn] | None = Field(
        default=None, max_length=50, description="Earlier turns; the last 3 exchanges are used to resolve follow-ups")


class Citation(BaseModel):
    label: str = ""            # "S1": the marker used in the answer text
    cited: bool = False        # the answer cites this source
    docId: str
    filename: str
    source: str
    page: int
    documentType: str
    excerpt: str
    textSnippet: str
    relevance: float           # reranker relevance to the question, 0..1


class GroundingOut(BaseModel):
    citedSources: list[str]
    invalidCitations: list[str]
    ungroundedNumbers: list[str]
    miscitedNumbers: list[str]
    unsupportedSentences: list[str]
    claims: int


class ChatAnswer(BaseModel):
    answer: str
    mode: Literal["llm", "extractive", "assistant", "no-evidence", "stopped"] = Field(
        description="llm: generated from the sources; extractive: evidence summary (model offline or disabled); "
                    "assistant: greeting; no-evidence: refused before generation; stopped: cancelled by the user")
    format: str
    evidenceStrength: Literal["high", "medium", "low"] | None = None
    refused: bool = False
    notice: str | None = None  # e.g. "LLM offline: showing top evidence."
    warnings: list[str] = []
    grounding: GroundingOut | None = None
    question: str = ""         # the question actually answered (follow-ups are rewritten to stand alone)
    model: str | None = None
    structured: dict[str, Any] | None = None  # work_order / checklist JSON
    confidence: float = Field(description="Deprecated: reranker relevance of the best evidence, not a probability "
                                          "that the answer is correct. Use evidenceStrength.")
    citations: list[Citation]
    assetTag: str
    queryId: int


class FeedbackRequest(BaseModel):
    feedback: Literal[1, -1] | None = None
