# IndusMind AI

**Industrial asset intelligence and root-cause analysis copilot.** IndusMind turns fragmented maintenance records, inspection reports, OEM manuals, safety procedures and operating data into a searchable evidence layer. It answers questions with source citations, builds an Asset 360° view, and drafts evidence-linked RCA briefs. Everything runs locally.

> **Project status:** the production upgrade is in progress ([docs/upgrade-plan.md](docs/upgrade-plan.md)). Phases 0–3 are done:
> - a PostgreSQL + pgvector backend with role-based accounts
> - background document processing
> - hybrid semantic search with reranking
> - answers written by a local language model (Qwen3-4B on the GPU) with checked citations
>
> The rebuilt UI and the fine-tuned model arrive in Phases 4 and 5.

## Features

- **Grounded answers from a local language model:** Qwen3-4B on your GPU answers from the retrieved passages only, with an `[S1]`-style citation after every fact. Answers stream as they are written, and you can stop them.
  - Every answer is checked automatically: numbers must appear in the sources, and citations must exist.
  - Each answer is labelled with an evidence strength (high, medium or low).
  - Follow-up questions keep their context.
  - Work orders and checklists come out as validated structured output.
- **Evidence search with citations:** hybrid semantic + keyword search with a cross-encoder reranker. Each citation shows the source document, page, excerpt and relevance.
- **Background processing:** uploads are queued and processed by a worker (OCR for scans and images). You can follow live progress.
- **Asset 360°:** a chronological timeline of dated failures, maintenance actions, measurements and readings per equipment tag, plus an equipment registry.
- **RCA briefs:** drafted by the model from the asset's evidence, with an observed problem, probable causes, recorded actions, investigation steps and preventive actions. Every item is cited. DOCX export.
- **Honest answers:** questions the documents cannot answer get "Insufficient evidence", not a guess. If the model is offline, answers fall back to the top evidence and say so.
- **Accounts and roles:** viewer, engineer and admin, with short-lived tokens, lockout, rate limits and an audit log.
- **Local and private:** PostgreSQL, Redis and the language model all run on your machine; no data leaves it.

## Quick start (Windows)

Requirements:
- Docker Desktop (running)
- Python 3.11 or 3.12
- Node.js LTS
- Ollama, with `ollama pull qwen3:4b-instruct-2507-q4_K_M`; an NVIDIA GPU with 4 GB is enough
- the retrieval models in `data/models/fastembed`, downloaded by `ml/setup/03_download_models_data.sh`

See [docs/setup.md](docs/setup.md).

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
| Generation | Qwen3-4B-Instruct-2507 (Q4_K_M) on Ollama with the GPU; versioned prompts, JSON-schema outputs, grounding checks |
| Frontend | React 19, TypeScript, Vite |
| Operations | Docker Compose, structured JSON logs, Prometheus metrics, health probes |
| AI (planned) | The same model fine-tuned with QLoRA on industrial RAG data (Phase 5) |

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
