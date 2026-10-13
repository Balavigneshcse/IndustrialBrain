param([switch]$DemoMode)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $Root "data\run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$StopScript = Join-Path $PSScriptRoot "stop-all.ps1"
if (Test-Path $StopScript) { powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StopScript | Out-Null }

function Start-IndusProcess($Name, $FilePath, $Arguments, $WorkingDirectory) {
    $Info = [System.Diagnostics.ProcessStartInfo]::new()
    if ([System.IO.Path]::GetExtension($FilePath) -ieq ".cmd") {
        $Info.FileName = "$env:SystemRoot\System32\cmd.exe"
        $Command = '"' + $FilePath + '" ' + (($Arguments | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' }) -join ' ')
        $Info.Arguments = '/d /c "' + $Command + '"'
    } else {
        $Info.FileName = $FilePath
        $Info.Arguments = (($Arguments | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' }) -join ' ')
    }
    $Info.WorkingDirectory = $WorkingDirectory
    $Info.UseShellExecute = $true
    $Info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $Process = [System.Diagnostics.Process]::Start($Info)
    Set-Content -LiteralPath (Join-Path $RunDir "$Name.pid") -Value $Process.Id
    Write-Host "Started $Name (PID $($Process.Id))"
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Python environment not found at .venv. Run scripts\setup.ps1 first." }

Write-Host "Using Python: $Python" -ForegroundColor Cyan

# Database and Redis containers, then schema migrations (and the demo accounts outside production)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start-services.ps1")
if ($LASTEXITCODE -ne 0) { throw "Database/Redis did not start" }
Push-Location $Root
try {
    & $Python -m server.app.cli migrate
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed" }
    if ($DemoMode) { & $Python -m server.app.cli seed-demo }
} finally { Pop-Location }

# FastAPI backend, and the background worker that processes uploads (thread pool: Windows-friendly)
Start-IndusProcess "backend" $Python @("-m", "uvicorn", "server.app.main:app", "--host", "127.0.0.1", "--port", "8000") $Root
Start-IndusProcess "worker" $Python @("-m", "celery", "-A", "server.app.workers.celery_app", "worker", "--pool=threads", "--concurrency=2", "-Q", "indusmind", "--loglevel=INFO") $Root

# Start React frontend
$Npm = (Get-Command npm.cmd -ErrorAction Stop).Source
Start-IndusProcess "frontend" $Npm @("run", "dev", "--", "--host", "127.0.0.1") (Join-Path $Root "frontend")

Write-Host "Waiting for services..."
$Healthy = $false
for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
    Start-Sleep -Seconds 3
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "health-check.ps1")
    if ($LASTEXITCODE -eq 0) { $Healthy = $true; break }
}
if (-not $Healthy) { throw "One or more services did not become healthy. Check logs and try health-check.ps1." }
Write-Host "Open http://localhost:5173" -ForegroundColor Green
