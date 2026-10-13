# IndusMind AI Setup Guide

## Install

1. Git for Windows
2. Node.js LTS
3. Python 3.11 or 3.12. During installation, enable **Add Python to PATH**.
4. Tesseract OCR and Poppler, only if scanned PDFs or images need OCR

The later upgrade phases also use Docker Desktop, WSL2 (Ubuntu) and Ollama; see [docs/UPGRADE_PLAN.md](docs/UPGRADE_PLAN.md).

## One-command setup

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

This installs and builds the frontend, creates `.venv` with the server dependencies, and runs the server tests.

## Manual startup

Terminal 1 (API on port 8000), from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt -r server\requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 (web UI on port 5173; `/api` is proxied to port 8000):

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Then visit `http://localhost:5173`. Interactive API docs are at `http://127.0.0.1:8000/docs`.

## Configuration

The server reads environment variables; see `.env.example` for the list. By default it stores data under `data/` (SQLite database, uploads, Chroma index).

## Ports

- React (Vite dev server): `5173`
- FastAPI: `8000`
