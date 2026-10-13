# Quick end-to-end check of a running server that has the sample corpus loaded.
# Defaults are the demo account seeded by server/database.py.
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "admin",
    [string]$Password = "Admin@123"
)
$ErrorActionPreference = "Stop"
$Body = @{ username = $Username; password = $Password } | ConvertTo-Json
$Login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" -ContentType "application/json" -Body $Body
$Headers = @{ Authorization = "Bearer $($Login.token)" }

$Dashboard = Invoke-RestMethod -Uri "$BaseUrl/api/dashboard" -Headers $Headers
if ($Dashboard.documents -lt 1) { throw "No documents indexed. Run load-sample-data.ps1." }

$Answer = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/chat/query" -Headers $Headers `
    -ContentType "application/json" -Body '{"question":"Why did Pump P-101 fail repeatedly in 2025?","assetTag":"P-101"}'
if (-not $Answer.answer -or $Answer.citations.Count -lt 1) { throw "Answer or citations missing." }

$Asset = Invoke-RestMethod -Uri "$BaseUrl/api/assets/P-101" -Headers $Headers
if ($Asset.evidenceChunks -lt 1) { throw "Asset 360 returned no evidence for P-101." }

$Rca = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/rca/P-101" -Headers $Headers
if ($Rca.probableCauses.Count -lt 1 -or ($Rca.probableCauses -join " ") -match "Insufficient") { throw "RCA causes missing." }

Write-Host "Smoke test passed: login, dashboard, answer with citations, Asset 360, and RCA." -ForegroundColor Green
Write-Host "Mode: $($Answer.mode); citations: $($Answer.citations.Count); asset chunks: $($Asset.evidenceChunks)"
