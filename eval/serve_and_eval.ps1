# Starts the server on a throwaway data folder (eval/.work/<Label>), loads the corpus,
# runs eval/run_eval.py, then stops the server. Your real data/ folder is never touched.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File eval\serve_and_eval.ps1 -Label after-phase0
#
# Needs EVAL_USERNAME / EVAL_PASSWORD for a user that the fresh server seeds on startup.
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$Port = 8010,
    [string]$LoadCorpus = "sample-data"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Create the venv first: python -m venv .venv; .venv\Scripts\pip install -r server\requirements.txt" }
if (-not $env:EVAL_USERNAME -or -not $env:EVAL_PASSWORD) { throw "Set EVAL_USERNAME and EVAL_PASSWORD first." }

$Work = Join-Path $Root "eval\.work\$Label"
if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $Work "uploads"), (Join-Path $Work "chroma") | Out-Null

$env:DATABASE_URL = "sqlite:///" + (Join-Path $Work "indusmind.db").Replace([char]92, [char]47)
$env:UPLOAD_DIR = Join-Path $Work "uploads"
$env:CHROMA_PATH = Join-Path $Work "chroma"

$Server = Start-Process $Python -ArgumentList "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", $Port `
    -RedirectStandardOutput (Join-Path $Work "server.out.log") -RedirectStandardError (Join-Path $Work "server.err.log") `
    -WindowStyle Hidden -PassThru
try {
    $Ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try { Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 | Out-Null; $Ready = $true; break }
        catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $Ready) { throw "Server did not start. See $Work\server.err.log" }
    & $Python (Join-Path $Root "eval\run_eval.py") --base-url "http://127.0.0.1:$Port" --label $Label --load-corpus $LoadCorpus
    if ($LASTEXITCODE -ne 0) { throw "run_eval.py failed with exit code $LASTEXITCODE" }
} finally {
    Stop-Process -Id $Server.Id -Force -ErrorAction SilentlyContinue
}
