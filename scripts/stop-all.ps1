# Stops what start-all.ps1 started. Ollama is stopped too (freeing the GPU, e.g. for training) if
# start-ollama.ps1 started it; an Ollama you started yourself is left running. -KeepOllama skips it.
param([switch]$KeepOllama)
$Root = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $Root "data\run"
foreach ($Name in @("frontend", "backend", "worker")) {
    $PidFile = Join-Path $RunDir "$Name.pid"
    if (Test-Path $PidFile) {
        $ProcessId = [int](Get-Content -LiteralPath $PidFile)
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "Stopped $Name"
    }
}
foreach ($Port in @(8000, 5173)) {
    $Conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($Conns) {
        foreach ($Conn in $Conns) {
            if ($Conn.OwningProcess -gt 0) {
                Stop-Process -Id $Conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped process ($($Conn.OwningProcess)) on port $Port"
            }
        }
    }
}
$OllamaPid = Join-Path $RunDir "ollama.pid"
if (-not $KeepOllama -and (Test-Path $OllamaPid)) {
    $ProcessId = [int](Get-Content -LiteralPath $OllamaPid)
    & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null   # /T: the model runner is a child process
    Remove-Item -LiteralPath $OllamaPid -Force
    Write-Host "Stopped Ollama (GPU memory released)"
}
