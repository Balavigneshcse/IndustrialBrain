# Architecture (current: after Phase 2)

The target production architecture is in [upgrade-plan.md](upgrade-plan.md) §3.

## Components

```mermaid
flowchart LR
    U[Viewer / Engineer / Admin] --> R[React + TypeScript<br/>Vite dev server :5173]
    R -->|/api proxy · Bearer token + refresh cookie| S[FastAPI server :8000<br/>auth, roles, rate limits, audit]
    S -->|queue job| Q[(Redis :6379<br/>job queue · rate limits)]
    Q --> W[Celery worker<br/>extract · OCR · chunk · tag · events · embed]
    S --> PG[(PostgreSQL 17 + pgvector<br/>users, documents, chunks + vectors + full text,<br/>asset events, asset registry, jobs, logs)]
    W --> PG
    S --> FILES[(Uploads<br/>original files)]
    W --> FILES
    S --> M[ONNX models on CPU<br/>bge-small embeddings · MiniLM reranker]
    W --> M
    S --> OBS[JSON logs · /metrics · /health/ready]
```

## Responsibility boundaries

- **React** presents the workflows and talks only to the API, through the hidden `/api` alias until the Phase 4 rebuild moves to `/api/v1`.
- **FastAPI** handles:
  - authentication, roles, rate limits and the audit log
  - accepting uploads: type check, size cap, de-duplication, then queueing
  - retrieval, answers, Asset 360, RCA and analytics
- **The worker** does the CPU-heavy ingestion:
  - text extraction, with OCR for scanned PDFs and images
  - structure-aware chunking: every dated log entry becomes its own chunk
  - per-chunk entities: equipment tags, ISO dates, measurements, failures and actions, with negations ignored
  - asset events from record documents
  - embeddings
- **Inline mode:** without Redis, the API does this work itself.
- **PostgreSQL** is the single store for relational data **and** the search index. Chunks, events and jobs are deleted with their document (`ON DELETE CASCADE`). Schema changes go through Alembic migrations, and the tests fail if the models and migrations differ.
- **No language model is called yet.** Answers are assembled from retrieved evidence (`mode: "extractive"`); Phase 3 adds Qwen3-4B.

## Retrieval

1. **Vector search:** the question's bge-small embedding against chunk embeddings (HNSW, cosine); top 30.
2. **Keyword search:** Postgres full text (`websearch_to_tsquery`, words OR-ed, ranked by `ts_rank_cd`); top 30.
3. **Fusion:** reciprocal rank fusion (k = 60) of both lists; the top 20 go on.
4. **Reranking:** the MiniLM cross-encoder scores each (question, passage) pair. The sigmoid of that score is the evidence's relevance, from 0 to 1.
5. **Threshold:** below `MIN_EVIDENCE_SCORE` (0.005), the answer is "insufficient evidence". The threshold is low on purpose, and [eval/README.md](../eval/README.md) explains why.

An asset-tag filter is an exact match on the chunk's subject equipment (GIN index). A question that names an exact uploaded filename is scoped to that file.

## Request and data flow

```mermaid
sequenceDiagram
    actor User
    participant UI as React
    participant API as FastAPI
    participant Q as Redis
    participant W as Worker
    participant DB as PostgreSQL + pgvector

    User->>UI: Upload document (engineer/admin)
    UI->>API: Multipart file + Bearer token
    API->>API: Check type (magic bytes), stream to disk (size cap), SHA-256
    alt Duplicate / wrong type / too large
        API-->>UI: 409 / 415 / 413
    else
        API->>DB: Document "queued" + job
        API->>Q: Enqueue job
        API-->>UI: 202 + jobId
        Q->>W: Job
        W->>DB: Chunks + vectors + asset events, document "ready" (or "failed" + reason)
        UI->>API: GET /documents/{id}/events (live status) or poll
    end

    User->>UI: Ask a question
    UI->>API: POST /chat/query
    alt Question names an asset no document mentions
        API-->>UI: "No indexed documents mention ..." (no citations)
    else
        API->>DB: Vector + keyword candidates (exact asset filter if given)
        API->>API: Fuse, rerank, apply evidence threshold, build extractive answer
        API->>DB: Log query (user, latency, retrieved chunk ids)
        API-->>UI: Answer + citations with relevance
    end
```

Access tokens expire after 15 minutes. The UI then calls `POST /auth/refresh` with the httpOnly cookie, which rotates, and retries the request.
