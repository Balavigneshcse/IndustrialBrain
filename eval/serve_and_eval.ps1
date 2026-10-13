# Runs the evaluation against a throwaway copy of the server:
#   - a freshly created and migrated PostgreSQL database "indusmind_eval" (needs: docker compose up -d db)
#   - a scratch upload folder eval/.work/<Label>/uploads
# then loads the corpus, runs eval/run_eval.py and stops the server. Your real database and data/
# folder are never touched.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File eval\serve_and_eval.ps1 -Label after-phase1
#
# The demo accounts are seeded into the eval database; EVAL_USERNAME / EVAL_PASSWORD default to
# the demo admin.
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$Port = 8010,
    [string]$LoadCorpus = "sample-data",
    [string]$Database = "indusmind_eval"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run scripts\setup.ps1 first (creates .venv)." }
if (-not $env:EVAL_USERNAME) { $env:EVAL_USERNAME = "admin" }
if (-not $env:EVAL_PASSWORD) { $env:EVAL_PASSWORD = "Admin@123" }

$Work = Join-Path $Root "eval\.work\$Label"
if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $Work "uploads") | Out-Null

# Create the scratch database while the main database is still the configured one (the CLI refuses
# to recreate the configured database), then point everything below at the scratch one.
& $Python -m server.app.cli recreate-database $Database
if ($LASTEXITCODE -ne 0) { throw "Could not recreate database $Database (is 'docker compose up -d db' running?)" }
$env:POSTGRES_DB = $Database
$env:UPLOAD_DIR = Join-Path $Work "uploads"
$env:CELERY_EAGER = "true"   # process uploads inline: deterministic, no worker needed
& $Python -m server.app.cli seed-demo | Out-Null
if ($LASTEXITCODE -ne 0) { throw "seed-demo failed" }

$Server = Start-Process $Python -ArgumentList "-m", "uvicorn", "server.app.main:app", "--host", "127.0.0.1", "--port", $Port `
    -RedirectStandardOutput (Join-Path $Work "server.out.log") -RedirectStandardError (Join-Path $Work "server.err.log") `
    -WindowStyle Hidden -PassThru
try {
    $Ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try { Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/health/ready" -TimeoutSec 2 | Out-Null; $Ready = $true; break }
        catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $Ready) { throw "Server did not become ready. See $Work\server.err.log" }
    & $Python (Join-Path $Root "eval\run_eval.py") --base-url "http://127.0.0.1:$Port" --label $Label --load-corpus $LoadCorpus
    if ($LASTEXITCODE -ne 0) { throw "run_eval.py failed with exit code $LASTEXITCODE" }
} finally {
    Stop-Process -Id $Server.Id -Force -ErrorAction SilentlyContinue
    Remove-Item Env:POSTGRES_DB, Env:UPLOAD_DIR, Env:CELERY_EAGER -ErrorAction SilentlyContinue
}
