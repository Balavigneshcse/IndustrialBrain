# IndusMind AI System Architecture (current)

This is what runs today. The target production architecture is in [../UPGRADE_PLAN.md](../UPGRADE_PLAN.md) §3.

```mermaid
flowchart LR
    U[Admin / Engineer] --> R[React + TypeScript<br/>Vite dev server :5173]
    R -->|/api proxy, JWT| S[FastAPI server :8000]
    S --> DB[(SQLite<br/>users, documents, query logs)]
    S --> FILES[(data/uploads<br/>original files)]
    S --> EX[Extraction: PDF, DOCX, CSV, XLSX, PPTX, HTML, EML<br/>Tesseract OCR fallback]
    EX --> ENT[Rule-based entities<br/>asset tags, dates, measurements, failures, actions]
    ENT --> CHUNK[Page-aware chunking]
    CHUNK --> V[(ChromaDB, embedded<br/>hashed bag-of-words vectors)]
    V --> RET[Evidence retrieval<br/>exact asset-tag filter]
    RET --> ANS[Extractive answer templates<br/>+ citations]
    ANS --> S
```

## Responsibility boundaries

- React presents the workflows and talks only to the FastAPI server.
- FastAPI handles authentication (JWT), document storage, extraction, indexing, retrieval, answers, Asset 360, RCA and analytics.
- SQLite stores users, document metadata and query logs.
- ChromaDB runs embedded and persistent under `data/chroma`.
- No language model is called yet. Answers are assembled from retrieved evidence (`mode: "extractive"`).
