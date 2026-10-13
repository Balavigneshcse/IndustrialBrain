# IndusMind AI

**Industrial Asset Intelligence & RCA Copilot**

IndusMind AI converts fragmented maintenance records, inspection reports, OEM guidance, safety procedures, and operating data into a searchable industrial knowledge layer. It answers questions with source citations, builds an Asset 360° view, and creates evidence-linked root-cause briefs.

> **Status:** Phases 0–1 of [docs/UPGRADE_PLAN.md](docs/UPGRADE_PLAN.md) are done. The backend runs on PostgreSQL + pgvector, with migrations, role-based accounts and a typed `/api/v1` contract.
>
> Answers are still **extractive**: they are assembled from the retrieved evidence by templates, and no language model is called yet. Semantic search (Phase 2), the Qwen3-4B model (Phases 3 and 5) and the rebuilt UI (Phase 4) come next.
>
> `IndusMind_Final_Presentation.pptx` and `PRESENTATION_SCRIPT.md` still describe the earlier plan (Spring Boot, LLaMA-3). They get updated in Phase 8.

## What works today

- **Evidence search with citations:** answers cite the source document, page and excerpt.
- **Honest refusals for unknown equipment:** questions about an asset no document mentions get "no indexed documents mention …".
- **Asset 360° and RCA briefs:** failures, measurements, actions, dates and evidence for an asset tag, with DOCX export.
- **Accounts and roles:** viewer (read and ask), engineer (upload, delete own documents, RCA), admin (users).
  - 15-minute access tokens with silent refresh; lockout after repeated failures; audit log.
- **Fully local:** PostgreSQL runs in Docker on this machine; nothing leaves it.

Known limits, fixed in Phase 2:
- Vectors are hashed bag-of-words (lexical, not semantic).
- Entities are tagged per document rather than per chunk. For example, the compressor record that says "No relation to Pump P-101" is attributed to P-101.
- Confidence figures are heuristics.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite (complete rebuild planned in Phase 4) |
| Backend API | Python, FastAPI, async SQLAlchemy 2, Alembic, JWT + rotating refresh cookies, Argon2id |
| Database | PostgreSQL 17 + pgvector (HNSW vectors, full-text index), in Docker |
| Retrieval | Page-aware chunking, rule-based entity extraction, vector search with exact asset-tag filters |
| Observability | Structured JSON logs with request ids, Prometheus `/metrics`, `/api/v1/health/ready` |

## Run it (Windows, PowerShell)

You need Docker Desktop (running), Python 3.11 or 3.12, and Node.js LTS.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\load-sample-data.ps1
```

`setup.ps1` does the following:
- creates `.env` with random secrets
- starts the database container
- installs dependencies, applies migrations and creates the demo accounts
- runs the tests

Then open [http://localhost:5173](http://localhost:5173). To stop, run `scripts\stop-all.ps1`; the database container keeps running until `docker compose stop`.

### Demo accounts (development only, created by `python -m server.app.cli seed-demo`)
| Role | Username | Password |
|---|---|---|
| Engineer | `engineer` | `Engineer@123` |
| Admin | `admin` | `Admin@123` |

For real users: `.venv\Scripts\python.exe -m server.app.cli create-user --username <name> --role admin`. The password is prompted, not stored in any file.

### Try asking
> "Why did Pump P-101 fail repeatedly in 2025?"
> "What safety steps apply before pump maintenance?"

## API

The contract is published at `http://127.0.0.1:8000/api/v1/openapi.json`, with interactive docs at `/api/v1/docs`. See [docs/api/API.md](docs/api/API.md).

## Tests and evaluation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\eval\serve_and_eval.ps1 -Label my-run
```

- **Tests:** they create their own scratch database (`indusmind_test`) on the Docker PostgreSQL. They cover auth, roles, the API contract, health, limits, and checks that the models match the migrations.
- **Eval:** runs the benchmark against a scratch database (`indusmind_eval`) and writes a report to `eval/reports/`.

## Repository structure

- `server/app/`: FastAPI application
  - `core/`: settings, security, logging, errors
  - `db/`: models and session
  - `api/v1/`: routes
  - `schemas/`: the API contract
  - `services/`: extraction, indexing, evidence store, answers
  - `cli.py`: admin commands
- `server/alembic/`: database migrations
- `server/tests/`: test suite
- `frontend/`: React application
- `eval/`: benchmark questions, evaluation harness, reports
- `ml/`: model training setup (Phase 5)
- `sample-data/`: synthetic industrial demonstration corpus
- `scripts/`: setup, start/stop, database, sample data, smoke test
- `docker-compose.yml`: PostgreSQL (and the optional API container)
- `docs/`: upgrade plan, API reference, architecture
