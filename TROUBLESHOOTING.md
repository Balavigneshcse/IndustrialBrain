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

## The API is down

Check `http://127.0.0.1:8000/api/health`. To see startup errors, run the server in the foreground:

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

## An upload shows FAILED

Hover over the badge, or read the message under it, to see the reason. Scanned PDFs and images need Tesseract OCR and Poppler, with `TESSERACT_CMD` set. The demo corpus is plain text and does not need OCR.

## Ports are already in use

Run `scripts\stop-all.ps1`, or stop the Node or Python servers using ports 5173 and 8000.

## Reset demo data

Stop all services, delete `data/indusmind.db`, and clear the contents of `data/chroma` and `data/uploads` while keeping the `.gitkeep` files.
