$Root = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $Root "data\run"
foreach ($Name in @("frontend", "backend", "ai-service")) {
    $PidFile = Join-Path $RunDir "$Name.pid"
    if (Test-Path $PidFile) {
        $ProcessId = [int](Get-Content -LiteralPath $PidFile)
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "Stopped $Name"
    }
}

