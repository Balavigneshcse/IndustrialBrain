"""PostgreSQL schema. Chunks and their vectors live next to the documents they came from, so the
relational data and the search index can never drift apart (they did with SQLite + Chroma)."""
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Computed, Date, DateTime, Float, ForeignKey, Index,
                        Integer, SmallInteger, String, Text, func, text)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

EMBEDDING_DIM = 384
EVENT_KINDS = ("failure", "action", "measurement", "reading")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")
ROLES = ("admin", "engineer", "viewer")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="role_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(256))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    failed_logins: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[int | None] = mapped_column(ForeignKey("refresh_tokens.id", ondelete="SET NULL"))
    user_agent: Mapped[str | None] = mapped_column(String(256))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("status IN ('queued', 'processing', 'ready', 'failed')", name="status_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True)  # uuid; also the stored file's name
    original_name: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), server_default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16))
    document_type: Mapped[str] = mapped_column(String(64), server_default="Industrial Document")
    asset_tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), server_default="{}")
    summary: Mapped[str] = mapped_column(Text, server_default="")
    error_message: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    uploaded_by: Mapped[User | None] = relationship(lazy="raise")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_chunks_asset_tags", "asset_tags", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(200), server_default="")
    word_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    # Full-text index for keyword search (used by hybrid retrieval in Phase 2).
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))
    asset_tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), server_default="{}")
    # failures / actions / dates / measurements extracted from the text
    entities: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(32))
    asset_tag: Mapped[str] = mapped_column(String(32), server_default="")
    confidence: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    retrieved_chunk_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    feedback: Mapped[int | None] = mapped_column(SmallInteger)
    # Generation details (Phase 3): what produced the answer, and how well it is grounded.
    standalone_question: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    evidence_strength: Mapped[str | None] = mapped_column(String(8))
    grounding: Mapped[dict | None] = mapped_column(JSONB)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    username: Mapped[str | None] = mapped_column(String(64))  # kept even if the user is deleted later
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Asset(Base):
    """Equipment registry (imported from the plant's equipment master list)."""
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200), server_default="")
    asset_class: Mapped[str] = mapped_column(String(64), server_default="")
    location: Mapped[str] = mapped_column(String(200), server_default="")
    criticality: Mapped[str] = mapped_column(String(16), server_default="")
    manufacturer: Mapped[str] = mapped_column(String(128), server_default="")
    notes: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AssetEvent(Base):
    """A dated failure, action, measurement or reading for one asset, with the sentence it came from."""
    __tablename__ = "asset_events"
    __table_args__ = (
        CheckConstraint(f"kind IN {EVENT_KINDS}", name="kind_valid"),
        Index("ix_asset_events_asset_tag_event_date", "asset_tag", "event_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_tag: Mapped[str] = mapped_column(String(32))
    event_date: Mapped[date | None] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(128))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(16))
    detail: Mapped[str] = mapped_column(Text, server_default="")
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    """Background work (document ingestion / re-indexing) with progress for the UI."""
    __tablename__ = "jobs"
    __table_args__ = (CheckConstraint(f"status IN {JOB_STATUSES}", name="status_valid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), server_default="queued")
    progress: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
