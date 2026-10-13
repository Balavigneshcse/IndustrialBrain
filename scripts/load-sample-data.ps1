# Uploads every file in sample-data/ to a running server.
# Defaults are the demo account seeded by server/database.py.
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "admin",
    [string]$Password = "Admin@123"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Body = @{ username = $Username; password = $Password } | ConvertTo-Json
$Login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" -ContentType "application/json" -Body $Body
$Files = Get-ChildItem -LiteralPath (Join-Path $Root "sample-data") -File
foreach ($File in $Files) {
    Write-Host "Uploading $($File.Name)..."
    $Result = & curl.exe --silent --show-error --fail `
        -H "Authorization: Bearer $($Login.token)" `
        -F "file=@$($File.FullName)" `
        "$BaseUrl/api/documents/upload"
    if ($LASTEXITCODE -ne 0) { throw "Upload failed for $($File.Name)" }
    $Status = ($Result | ConvertFrom-Json).status
    if ($Status -ne "ready") { throw "$($File.Name) was not indexed (status: $Status)" }
}
Write-Host "Sample corpus loaded." -ForegroundColor Green
