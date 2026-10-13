# IndusMind AI Setup Guide

## Install

1. Git for Windows
2. Docker Desktop (runs PostgreSQL + pgvector and Redis)
3. Node.js LTS
4. Python 3.11 or 3.12. During installation, enable **Add Python to PATH**.
5. Tesseract OCR and Poppler on Windows, only if a natively running worker must OCR scanned PDFs or images. The Docker worker image already includes them.

The model-training phases also use WSL2 (Ubuntu) and Ollama; see [upgrade-plan.md](upgrade-plan.md).

## Retrieval models

The server embeds and reranks text with two small ONNX models that run on the CPU. They must be in `data/models/fastembed`, and the server never downloads them at runtime. Fetch them once (with the datasets) from the repository root:

```powershell
wsl -d Ubuntu -- bash ml/setup/03_download_models_data.sh
```

Or copy an existing `data/models/fastembed` folder from a teammate. `/api/v1/health/ready` reports `models: error` if they are missing.

## One-command setup

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

This does the following:
1. creates `.env` with random secrets (`scripts\init-env.ps1`; an existing file is never overwritten)
2. starts the database and Redis containers (`scripts\start-services.ps1`)
3. installs and builds the frontend
4. creates `.venv` with the server dependencies
5. applies database migrations and creates the demo accounts
6. runs the tests

`scripts\start-all.ps1` then starts the API, the **worker** and the web UI.

## Manual startup

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\init-env.ps1
docker compose up -d
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt -r server\requirements-dev.txt
.\.venv\Scripts\python.exe -m server.app.cli migrate
.\.venv\Scripts\python.exe -m server.app.cli seed-demo
.\.venv\Scripts\python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
```

Second terminal, the background worker that processes uploads. `--pool=threads` is needed on Windows.

```powershell
.\.venv\Scripts\python.exe -m celery -A server.app.workers.celery_app worker --pool=threads --concurrency=2 -Q indusmind --loglevel=INFO
```

Third terminal (web UI on port 5173; `/api` is proxied to port 8000):

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Then visit `http://localhost:5173`. The API docs are at `http://127.0.0.1:8000/api/v1/docs`.

Without Redis (`REDIS_URL` unset) or with `CELERY_EAGER=true`, uploads are processed **inline** in the API process and no worker is needed. This is handy for quick checks; the tests and eval runs use it.

## Running everything in Docker

```powershell
docker compose --profile full up -d --build
```

This runs the API and the worker from one image, alongside the database and Redis:
- Tesseract and Poppler are included in the image.
- Both containers run as a non-root user.
- The API applies migrations on start.
- Uploads are kept in a named volume.
- The retrieval models are mounted read-only from `data/models/fastembed`.

## Admin commands

```powershell
.\.venv\Scripts\python.exe -m server.app.cli create-user --username alice --role admin --display-name "Alice"
.\.venv\Scripts\python.exe -m server.app.cli import-assets sample-data\registry\asset-registry.csv   # equipment registry
.\.venv\Scripts\python.exe -m server.app.cli reindex             # re-extract and re-embed all stored documents
.\.venv\Scripts\python.exe -m server.app.cli import-legacy       # re-index documents from the old SQLite data/indusmind.db
.\.venv\Scripts\python.exe -m server.app.cli migrate
```

After importing the registry, re-index: once a registry exists, only registered equipment tags are recognised in documents.

## Configuration

Settings come from `.env` (see `.env.example`) and environment variables, which take precedence. In production (`INDUSMIND_ENV=production`), the server refuses to start without a real `SECRET_KEY`, a database password and `COOKIE_SECURE=true`.

## Ports

- React (Vite dev server): `5173`
- FastAPI: `8000`
- PostgreSQL (container): `127.0.0.1:5433`. 5432 is often taken by a local PostgreSQL install.
- Redis (container): `127.0.0.1:6379`
