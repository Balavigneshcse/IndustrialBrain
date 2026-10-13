# IndusMind AI Setup Guide

## Install

1. Git for Windows
2. Docker Desktop (runs PostgreSQL + pgvector)
3. Node.js LTS
4. Python 3.11 or 3.12. During installation, enable **Add Python to PATH**.
5. Tesseract OCR and Poppler, only if scanned PDFs or images need OCR

The later upgrade phases also use WSL2 (Ubuntu) and Ollama; see [docs/UPGRADE_PLAN.md](docs/UPGRADE_PLAN.md).

## One-command setup

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

This does the following:
1. creates `.env` with random secrets (`scripts\init-env.ps1`; an existing file is never overwritten)
2. starts the database container (`scripts\start-db.ps1`)
3. installs and builds the frontend
4. creates `.venv` with the server dependencies
5. applies database migrations and creates the demo accounts
6. runs the tests

## Manual startup

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\init-env.ps1
docker compose up -d db
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt -r server\requirements-dev.txt
.\.venv\Scripts\python.exe -m server.app.cli migrate
.\.venv\Scripts\python.exe -m server.app.cli seed-demo
.\.venv\Scripts\python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
```

Second terminal (web UI on port 5173; `/api` is proxied to port 8000):

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Then visit `http://localhost:5173`. The API docs are at `http://127.0.0.1:8000/api/v1/docs`.

## Running the API in Docker instead

```powershell
docker compose --profile full up -d --build
```

The container applies migrations on start, runs as a non-root user and keeps uploads in a named volume.

## Admin commands

```powershell
.\.venv\Scripts\python.exe -m server.app.cli create-user --username alice --role admin --display-name "Alice"
.\.venv\Scripts\python.exe -m server.app.cli import-legacy      # re-index documents from the old SQLite data/indusmind.db
.\.venv\Scripts\python.exe -m server.app.cli migrate
```

## Configuration

Settings come from `.env` (see `.env.example`) and environment variables, which take precedence. In production (`INDUSMIND_ENV=production`), the server refuses to start without a real `SECRET_KEY`, a database password and `COOKIE_SECURE=true`.

## Ports

- React (Vite dev server): `5173`
- FastAPI: `8000`
- PostgreSQL (container): `127.0.0.1:5433`. 5432 is often taken by a local PostgreSQL install.
