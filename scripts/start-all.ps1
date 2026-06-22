param([switch]$DemoMode)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $Root "data\run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

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
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Process = [System.Diagnostics.Process]::Start($Info)
    Set-Content -LiteralPath (Join-Path $RunDir "$Name.pid") -Value $Process.Id
    Write-Host "Started $Name (PID $($Process.Id))"
}

$Python = Join-Path $Root "ai-service\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run scripts\setup.ps1 first." }

Start-IndusProcess "ai-service" $Python @("run.py") (Join-Path $Root "ai-service")

$BackendArgs = @("spring-boot:run")
if ($DemoMode) { $BackendArgs += "-Dspring-boot.run.profiles=demo" }
$Maven = (Get-Command mvn.cmd -ErrorAction Stop).Source
$Npm = (Get-Command npm.cmd -ErrorAction Stop).Source
Start-IndusProcess "backend" $Maven $BackendArgs (Join-Path $Root "backend")
Start-IndusProcess "frontend" $Npm @("run", "dev", "--", "--host", "127.0.0.1") (Join-Path $Root "frontend")

Write-Host "Waiting for services..."
$Healthy = $false
for ($Attempt = 1; $Attempt -le 12; $Attempt++) {
    Start-Sleep -Seconds 3
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "health-check.ps1")
    if ($LASTEXITCODE -eq 0) { $Healthy = $true; break }
}
if (-not $Healthy) { throw "One or more services did not become healthy. Check data\run and run health-check.ps1." }
Write-Host "Open http://localhost:5173" -ForegroundColor Green
