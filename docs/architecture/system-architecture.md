# IndusMind AI System Architecture (current: after Phase 1)

The target production architecture is in [../UPGRADE_PLAN.md](../UPGRADE_PLAN.md) §3.

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
