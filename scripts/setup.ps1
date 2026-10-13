$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "IndusMind AI setup" -ForegroundColor Cyan

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js LTS is required." }

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Py = Get-Command py -ErrorAction SilentlyContinue
    if ($Py) { $PythonExe = "py"; $PythonArgs = @("-3.12") }
    else { throw "Python 3.11 or 3.12 is required. Install it and enable Add Python to PATH." }
} else {
    $PythonExe = "python"; $PythonArgs = @()
}

Push-Location "$Root\frontend"
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally { Pop-Location }

# Backend: FastAPI server in server/, using the root .venv that start-all.ps1 looks for.
Push-Location $Root
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        & $PythonExe @PythonArgs -m venv .venv
    }
    & ".\.venv\Scripts\python.exe" -m pip install -r server\requirements.txt -r server\requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    & ".\.venv\Scripts\python.exe" -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Server tests failed" }
} finally { Pop-Location }

Write-Host "Setup complete. Run scripts\start-all.ps1, then scripts\load-sample-data.ps1" -ForegroundColor Green
