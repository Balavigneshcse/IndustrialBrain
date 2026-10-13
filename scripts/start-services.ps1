# Starts the PostgreSQL + pgvector and Redis containers (docker-compose.yml) and waits until healthy.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker is not running. Start Docker Desktop and try again." }
    & docker compose up -d db redis
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
    foreach ($Service in "db", "redis") {
        $Container = (& docker compose ps -q $Service)
        $Healthy = $false
        for ($i = 0; $i -lt 60; $i++) {
            if ((& docker inspect -f "{{.State.Health.Status}}" $Container 2>$null) -eq "healthy") { $Healthy = $true; break }
            Start-Sleep -Seconds 2
        }
        if (-not $Healthy) { throw "$Service did not become healthy within 2 minutes (docker compose logs $Service)." }
    }
    Write-Host "Database and Redis are healthy." -ForegroundColor Green
} finally { Pop-Location }
