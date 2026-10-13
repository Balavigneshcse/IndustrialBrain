# Architecture (current: after Phase 1)

The target production architecture is in [upgrade-plan.md](upgrade-plan.md) §3.

## Components

```mermaid
flowchart LR
    U[Viewer / Engineer / Admin] --> R[React + TypeScript<br/>Vite dev server :5173]
    R -->|/api proxy · Bearer token + refresh cookie| S[FastAPI server :8000<br/>auth, roles, rate limits, audit]
    S --> PG[(PostgreSQL 17 + pgvector<br/>users, sessions, documents,<br/>chunks + vectors + full-text,<br/>query and audit logs)]
    S --> FILES[(data/uploads<br/>original files)]
    S --> EX[Extraction: PDF, DOCX, CSV, XLSX, PPTX, HTML, EML<br/>Tesseract OCR fallback · worker thread]
    EX --> ENT[Rule-based entities<br/>asset tags, dates, measurements, failures, actions]
    ENT --> CHUNK[Page-aware chunking]
    CHUNK --> PG
    PG --> RET[Vector search, HNSW cosine<br/>exact asset-tag filter]
    RET --> ANS[Extractive answer templates + citations]
    ANS --> S
    S --> OBS[JSON logs · /metrics · /health/ready]
```

## Responsibility boundaries

- React presents the workflows and talks only to the API, through the hidden `/api` alias until the Phase 4 rebuild moves to `/api/v1`.
- FastAPI handles:
  - authentication: short-lived JWT access tokens, rotating httpOnly refresh cookies, lockout
  - role checks and rate limits
  - document storage, extraction, indexing, retrieval and answers
  - Asset 360, RCA and analytics
- PostgreSQL is the single store for relational data **and** the search index. Chunks are deleted with their document (`ON DELETE CASCADE`), so they can't drift apart.
- Schema changes go through Alembic migrations. The test suite fails if the models and migrations differ.
- No language model is called yet. Answers are assembled from retrieved evidence (`mode: "extractive"`).

## Request and data flow

```mermaid
sequenceDiagram
    actor User
    participant UI as React
    participant API as FastAPI
    participant DB as PostgreSQL + pgvector

    User->>UI: Sign in
    UI->>API: POST /auth/login
    API->>DB: Verify Argon2id hash, reset failures, store refresh-token hash, audit
    API-->>UI: Access token (15 min) + httpOnly refresh cookie

    User->>UI: Upload document (engineer/admin)
    UI->>API: Multipart file + Bearer token
    API->>API: Stream to disk (size cap, SHA-256), extract + chunk in a worker thread
    alt Text extracted
        API->>DB: Document READY + chunks with vectors (one transaction)
    else Unreadable
        API->>DB: Document FAILED + reason (nothing indexed)
    end
    API-->>UI: Document record

    User->>UI: Ask a question
    UI->>API: POST /chat/query
    alt Access token expired
        API-->>UI: 401
        UI->>API: POST /auth/refresh (cookie rotates)
        API-->>UI: New access token, then the request is retried
    end
    alt Question names an asset no document mentions
        API-->>UI: "No indexed documents mention ..." (no citations)
    else
        API->>DB: Vector search (exact asset-tag filter if given)
        API->>API: Build extractive answer from evidence
        API->>DB: Log query (user, latency, retrieved chunk ids)
        API-->>UI: Answer + citations + heuristic confidence
    end
```
