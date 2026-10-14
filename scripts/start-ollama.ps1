# Starts Ollama with the GPU settings from docs/upgrade-plan.md §2.2 (set for this process only, nothing is
# changed system-wide) and loads the answer model into VRAM. An Ollama that is already running is reused;
# its settings are then whatever it was started with.
param([string]$Model = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $Root "data\run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$BaseUrl = "http://127.0.0.1:11434"

if (-not $Model) {
    $EnvFile = Join-Path $Root ".env"
    $Line = if (Test-Path $EnvFile) { Select-String -LiteralPath $EnvFile -Pattern '^\s*LLM_MODEL\s*=\s*(\S+)' | Select-Object -First 1 }
    $Model = if ($Line) { $Line.Matches[0].Groups[1].Value } else { "qwen3:4b-instruct-2507-q4_K_M" }
}

function Test-Ollama {
    try { Invoke-RestMethod "$BaseUrl/api/version" -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

if (Test-Ollama) {
    Write-Host "Ollama is already running; reusing it." -ForegroundColor Yellow
} else {
    $Ollama = (Get-Command ollama.exe -ErrorAction SilentlyContinue).Source
    if (-not $Ollama) { $Ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe" }
    if (-not (Test-Path $Ollama)) { throw "Ollama is not installed (https://ollama.com/download)." }
    $env:OLLAMA_HOST = "127.0.0.1:11434"
    $env:OLLAMA_NUM_PARALLEL = "2"         # two answers stream at the same time
    $env:OLLAMA_FLASH_ATTENTION = "1"
    $env:OLLAMA_KV_CACHE_TYPE = "q8_0"     # halves the KV cache (needs flash attention)
    $env:OLLAMA_KEEP_ALIVE = "-1"          # keep the model loaded: no cold starts
    $env:OLLAMA_MAX_QUEUE = "32"
    $env:OLLAMA_CONTEXT_LENGTH = "4096"
    $Log = Join-Path $RunDir "ollama.log"
    $Process = Start-Process -FilePath $Ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru `
        -RedirectStandardError $Log -RedirectStandardOutput (Join-Path $RunDir "ollama.out.log")
    Set-Content -LiteralPath (Join-Path $RunDir "ollama.pid") -Value $Process.Id
    for ($i = 0; $i -lt 30 -and -not (Test-Ollama); $i++) { Start-Sleep -Milliseconds 500 }
    if (-not (Test-Ollama)) { throw "Ollama did not start; see $Log" }
    Write-Host "Started Ollama (PID $($Process.Id)); log: $Log"
}

$Tags = (Invoke-RestMethod "$BaseUrl/api/tags").models.name
if ($Tags -notcontains $Model) {
    Write-Warning "Model $Model is not installed. Run: ollama pull $Model   (answers fall back to extractive mode until then)"
    exit 0
}

# Load the model with the same options the API sends (all layers on the GPU, 4K context), so the first
# question does not pay the load time and Ollama does not reload it for a different context size.
$Body = @{ model = $Model; prompt = ""; keep_alive = -1; options = @{ num_gpu = 99; num_ctx = 4096 } } | ConvertTo-Json
Invoke-RestMethod "$BaseUrl/api/generate" -Method Post -Body $Body -ContentType "application/json" -TimeoutSec 180 | Out-Null
$Loaded = (Invoke-RestMethod "$BaseUrl/api/ps").models | Where-Object { $_.name -eq $Model }
if ($Loaded) {
    $Gpu = if ($Loaded.size) { [math]::Round(100 * $Loaded.size_vram / $Loaded.size) } else { 0 }
    Write-Host ("Model {0} loaded: {1:N1} GB, {2}% on the GPU." -f $Model, ($Loaded.size / 1GB), $Gpu) -ForegroundColor Green
    if ($Gpu -lt 100) { Write-Warning "Part of the model is on the CPU (slower). Close GPU-heavy apps and run this script again." }
}
