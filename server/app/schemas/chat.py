from typing import Literal

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    role: str | None = None
    content: str | None = None


class ChatQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    assetTag: str | None = Field(default="", max_length=32)
    desiredFormat: str | None = Field(default="quick_answer", max_length=32)
    history: list[ConversationTurn] | None = Field(default=None, max_length=50)


class Citation(BaseModel):
    docId: str
    filename: str
    source: str
    page: int
    documentType: str
    excerpt: str
    textSnippet: str
    relevance: float


class ChatAnswer(BaseModel):
    answer: str
    mode: str
    format: str
    confidence: float
    citations: list[Citation]
    assetTag: str
    queryId: int


class FeedbackRequest(BaseModel):
    feedback: Literal[1, -1] | None = None
