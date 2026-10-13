# IndusMind AI

**Industrial asset intelligence and root-cause analysis copilot.** IndusMind turns fragmented maintenance records, inspection reports, OEM manuals, safety procedures and operating data into a searchable evidence layer. It answers questions with source citations, builds an Asset 360° view, and drafts evidence-linked RCA briefs. Everything runs locally.

> **Project status:** the production upgrade is in progress ([docs/upgrade-plan.md](docs/upgrade-plan.md)). Phases 0–2 are done: a PostgreSQL + pgvector backend with role-based accounts, background document processing, and hybrid semantic search with reranking.
>
> Answers are currently **extractive** (assembled from the retrieved evidence, with no language model yet). The fine-tuned Qwen3-4B model and the rebuilt UI arrive in Phases 3–5.

## Features

- **Evidence search with citations:** hybrid semantic + keyword search with a cross-encoder reranker. Every answer cites its source document, page, excerpt and relevance.
- **Background processing:** uploads are queued and processed by a worker (OCR for scans and images). You can follow live progress.
- **Asset 360°:** a chronological timeline of dated failures, maintenance actions, measurements and readings per equipment tag, plus an equipment registry.
- **RCA briefs:** observed problem, probable causes, recorded actions, investigation steps and evidence, with DOCX export.
- **Honest answers:** questions about equipment that no document mentions are refused, not guessed.
- **Accounts and roles:** viewer, engineer and admin, with short-lived tokens, lockout, rate limits and an audit log.
- **Local and private:** PostgreSQL runs in Docker on your machine; no data leaves it.

## Quick start (Windows)

Requirements: Docker Desktop (running), Python 3.11 or 3.12, Node.js LTS, and the retrieval models in `data/models/fastembed` (downloaded by `ml/setup/03_download_models_data.sh`; see [docs/setup.md](docs/setup.md)).

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\load-sample-data.ps1
```

Open <http://localhost:5173> and sign in with the development demo account `admin` / `Admin@123` (or `engineer` / `Engineer@123`). Try: *"Why did Pump P-101 fail repeatedly in 2025?"*

Manual setup, the API container, admin commands and configuration are covered in [docs/setup.md](docs/setup.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/setup.md](docs/setup.md) | Installation, configuration, admin commands, ports |
| [docs/architecture.md](docs/architecture.md) | Components and request/data flow |
| [docs/api.md](docs/api.md) | REST API v1, roles, errors, rate limits (live contract at `/api/v1/docs`) |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common problems and fixes |
| [docs/upgrade-plan.md](docs/upgrade-plan.md) | Production upgrade plan, model choice, phase status |
| [eval/README.md](eval/README.md) | Benchmark, metrics and results |
| [ml/README.md](ml/README.md) | Model training setup |
| [docs/presentation/](docs/presentation) | Team slides and script (being updated in Phase 8) |

## Technology

| Layer | Stack |
|---|---|
| Backend | Python, FastAPI, async SQLAlchemy 2, Alembic, Argon2id, JWT + rotating refresh cookies |
| Data | PostgreSQL 17 + pgvector (HNSW vectors, full-text index), Redis (job queue) |
| Retrieval | bge-small embeddings + MiniLM cross-encoder (ONNX on CPU via fastembed), Celery worker, Tesseract OCR |
| Frontend | React 19, TypeScript, Vite |
| Operations | Docker Compose, structured JSON logs, Prometheus metrics, health probes |
| AI (planned) | Qwen3-4B-Instruct fine-tuned with QLoRA, served by Ollama (Phases 3 and 5) |

## Project structure

```
├── server/           FastAPI backend: app/ (api, core, db, schemas, services), alembic/, tests/
├── frontend/         React web UI
├── ml/               model training setup
├── eval/             benchmark, evaluation harness and reports
├── sample-data/      synthetic demonstration corpus
├── scripts/          Windows setup, start/stop, sample-data and smoke-test scripts
├── docs/             documentation and presentation
├── docker-compose.yml
├── pyproject.toml    Python tool configuration
└── .env.example      settings template
```

## Development

```powershell
.\.venv\Scripts\python.exe -m pytest -q                                                      # backend tests (needs the database container)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\eval\serve_and_eval.ps1 -Label dev   # benchmark run
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). The documents in `sample-data/` are synthetic.
