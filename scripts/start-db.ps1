# Starts the PostgreSQL + pgvector container (docker-compose.yml) and waits until it is healthy.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker is not running. Start Docker Desktop and try again." }
    & docker compose up -d db
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
    $Container = (& docker compose ps -q db)
    for ($i = 0; $i -lt 60; $i++) {
        $Health = & docker inspect -f "{{.State.Health.Status}}" $Container 2>$null
        if ($Health -eq "healthy") { Write-Host "Database is healthy." -ForegroundColor Green; exit 0 }
        Start-Sleep -Seconds 2
    }
    throw "Database did not become healthy within 2 minutes (docker compose logs db)."
} finally { Pop-Location }
