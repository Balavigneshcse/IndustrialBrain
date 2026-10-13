# Troubleshooting

## PowerShell blocks scripts

Use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
```

## `npm.ps1` cannot be loaded

Use `npm.cmd`, as the project scripts do.

## Python is not found, or start-all says `.venv` is missing

Install Python 3.11 or 3.12 with **Add Python to PATH** enabled, reopen the terminal, and run `scripts\setup.ps1`.

## "Docker is not running" or the database does not start

Start Docker Desktop, wait until it says it is running, then run `scripts\start-services.ps1` (database and Redis). To see what went wrong, run `docker compose logs db`.

## Port 5432 is already in use

That is usually a PostgreSQL installed directly on Windows. IndusMind's database container uses **5433** on purpose (`POSTGRES_PORT` in `.env`).

## The API is down or not ready

Check `http://127.0.0.1:8000/api/v1/health/ready`. It reports each dependency (database, pgvector, uploads). To see startup errors, run the server in the foreground:

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
```

If it says a migration is missing, run `.\.venv\Scripts\python.exe -m server.app.cli migrate`.

## Sign-in fails

- `401 Incorrect username or password`: in development, run `.\.venv\Scripts\python.exe -m server.app.cli seed-demo` to (re)create the demo accounts.
- `423 Account locked`: wait 15 minutes, or have an admin reset the password, which also unlocks the account.
- `429 Too many requests`: wait for the number of seconds in `Retry-After`.

## The tests cannot connect to PostgreSQL

The tests create their own database (`indusmind_test`) on the Docker database. Start it with `docker compose up -d db`.

## Uploads stay "queued"

No worker is processing the queue. `/api/v1/health/ready` then shows `worker: error` ("no heartbeat"). Start it with `scripts\start-all.ps1`, or manually:

```powershell
.\.venv\Scripts\python.exe -m celery -A server.app.workers.celery_app worker --pool=threads --concurrency=2 -Q indusmind --loglevel=INFO
```

For a quick check without a worker, set `CELERY_EAGER=true` (or unset `REDIS_URL`), and uploads are processed inside the API.

## Readiness says `models: error`

The retrieval models are missing from `data/models/fastembed`. Run `wsl -d Ubuntu -- bash ml/setup/03_download_models_data.sh`, or copy the folder from a teammate.

If the folder exists but Windows cannot read the files (OSError), they are WSL symlinks from an older download. Re-run the script: it now replaces the symlinks with real files.

## Search found nothing for an older document

Documents indexed before Phase 2 used the old hashed vectors. Run `.\.venv\Scripts\python.exe -m server.app.cli reindex` once.

## An upload shows FAILED

Hover over the badge, or read the message under it, to see the reason. Scanned PDFs and images need Tesseract OCR and Poppler, with `TESSERACT_CMD` set. The demo corpus is plain text and does not need OCR.

## Ports are already in use

Run `scripts\stop-all.ps1`, or stop the Node or Python servers using ports 5173 and 8000.

## Reset demo data

This deletes all documents, users and logs in the database:

```powershell
docker compose down -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Uploaded files are in `data/uploads`. Clear that folder too, but keep the `.gitkeep` file.
