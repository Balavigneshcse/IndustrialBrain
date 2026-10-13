# IndusMind AI

**Industrial Asset Intelligence & RCA Copilot**

IndusMind AI converts fragmented maintenance records, inspection reports, OEM guidance, safety procedures, and operating data into a searchable industrial knowledge layer. It answers questions with source citations, builds an Asset 360° view, and creates evidence-linked root-cause briefs.

> **Status:** Phase 0 of [docs/UPGRADE_PLAN.md](docs/UPGRADE_PLAN.md) is done. Answers are **extractive**: they are assembled from the retrieved evidence by templates, and no language model is called yet. The fine-tuned Qwen3-4B model, Postgres/pgvector and the rest of the production stack arrive in later phases.
>
> `IndusMind_Final_Presentation.pptx` and `PRESENTATION_SCRIPT.md` still describe the earlier plan (Spring Boot, LLaMA-3). They get updated in Phase 8.

## What works today

- **Evidence search with citations:** answers cite the source document, page and excerpt, retrieved from a local ChromaDB index.
- **Honest refusals for unknown equipment:** questions about an asset that no document mentions get "no indexed documents mention …" instead of another asset's data.
- **Asset 360°:** failures, measurements, maintenance actions, dates and sources for an asset tag.
- **RCA brief:** observed problem, probable causes, recorded actions, investigation steps and evidence, with DOCX export.
- **Fully local:** no cloud services; documents and the index stay on this machine.

Known limits, fixed in later phases:
- Vectors are hashed bag-of-words (lexical, not semantic).
- Entities are tagged per document rather than per chunk. For example, the compressor record that says "No relation to Pump P-101" is attributed to P-101.
- Confidence figures are heuristics.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, custom CSS |
| Backend API | Python, FastAPI, SQLAlchemy + SQLite, JWT auth |
| Retrieval | ChromaDB (embedded), page-aware chunking, rule-based entity extraction |
| Answers | Extractive templates over retrieved evidence (LLM planned: Qwen3-4B-Instruct via Ollama) |

## Run it (Windows, PowerShell)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\load-sample-data.ps1
```

Then open [http://localhost:5173](http://localhost:5173). To stop everything, run `scripts\stop-all.ps1`.

### Demo accounts (seeded on first start; replaced by a create-admin command in Phase 1)
| Role | Username | Password |
|---|---|---|
| Engineer | `engineer` | `Engineer@123` |
| Admin | `admin` | `Admin@123` |

### Try asking
> "Why did Pump P-101 fail repeatedly in 2025?"
> "What safety steps apply before pump maintenance?"

## Tests and evaluation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:EVAL_USERNAME = "admin"; $env:EVAL_PASSWORD = "Admin@123"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\eval\serve_and_eval.ps1 -Label my-run
```

The eval runs the 10 benchmark questions plus honesty probes against a throwaway copy of the server and writes a report to `eval/reports/`.

## Repository structure

- `server/`: FastAPI API (auth, documents, chat, assets, RCA, analytics) and its tests
- `frontend/`: React application
- `eval/`: benchmark questions, evaluation harness, reports
- `ml/`: model training setup (Phase 5): WSL setup scripts and the pinned training environment
- `sample-data/`: synthetic industrial demonstration corpus
- `scripts/`: setup, start/stop, sample-data loading, smoke test
- `docs/`: upgrade plan, API reference, architecture
